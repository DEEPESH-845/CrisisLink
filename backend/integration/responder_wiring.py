"""Responder App ↔ Backend Wiring.

Documents and implements the wiring between the Responder App
(Flutter Mobile) and backend services via Firebase RTDB and FCM.

Dispatch notification flow:
    Operator confirms dispatch → Dispatch Service → FCM push → Responder App

Status update propagation:
    Responder App → Firebase RTDB /units/{unit_id}/status → Operator Dashboard

GPS location consumption:
    Responder App → Firebase RTDB /units/{unit_id}/location → Dispatch Engine

Requirements: 4.5, 7.1, 7.5, 7.6, 8.1, 8.3
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from shared.firebase.paths import unit_location, unit_status
from shared.models import UnitStatus
from speech_ingestion.audit_logger import AuditEntry, AuditLogger, MockAuditLogger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Valid status transitions (Property 10 / Req 7.4, 8.2)
# ---------------------------------------------------------------------------

VALID_STATUS_TRANSITIONS: dict[UnitStatus, set[UnitStatus]] = {
    UnitStatus.AVAILABLE: {UnitStatus.DISPATCHED},
    UnitStatus.DISPATCHED: {UnitStatus.ON_SCENE},
    UnitStatus.ON_SCENE: {UnitStatus.RETURNING},
    UnitStatus.RETURNING: {UnitStatus.AVAILABLE},
}


def is_valid_transition(current: UnitStatus, target: UnitStatus) -> bool:
    """Return True if *current* → *target* is a valid status transition."""
    return target in VALID_STATUS_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# FCM notification trigger
# ---------------------------------------------------------------------------


@runtime_checkable
class FCMNotifier(Protocol):
    """Sends push notifications via Firebase Cloud Messaging."""

    async def send_dispatch_notification(
        self,
        unit_id: str,
        call_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Send a dispatch push notification. Returns True on success."""
        ...


@dataclass
class FCMNotificationResult:
    """Outcome of an FCM dispatch notification."""

    unit_id: str
    call_id: str
    sent: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


async def trigger_dispatch_notification(
    unit_id: str,
    call_id: str,
    emergency_type: str,
    severity: str,
    caller_location: dict[str, float],
    fcm_notifier: FCMNotifier,
) -> FCMNotificationResult:
    """Send an FCM push notification to the assigned responder.

    Triggered when the operator confirms a dispatch. The notification
    includes emergency type, severity, and estimated caller location
    (Req 7.1).

    Parameters
    ----------
    unit_id : str
        The dispatched unit's identifier.
    call_id : str
        The call session identifier.
    emergency_type : str
        The classified emergency type.
    severity : str
        The classified severity level.
    caller_location : dict
        ``{"lat": float, "lng": float}`` of the caller.
    fcm_notifier : FCMNotifier
        The FCM client to send the notification through.

    Returns
    -------
    FCMNotificationResult
    """
    result = FCMNotificationResult(unit_id=unit_id, call_id=call_id)

    payload = {
        "call_id": call_id,
        "unit_id": unit_id,
        "emergency_type": emergency_type,
        "severity": severity,
        "caller_location": caller_location,
        "action": "dispatch",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    result.payload = payload

    try:
        sent = await fcm_notifier.send_dispatch_notification(
            unit_id=unit_id, call_id=call_id, payload=payload
        )
        result.sent = sent
    except Exception as exc:
        logger.error(
            "FCM notification failed for unit %s, call %s: %s",
            unit_id, call_id, exc,
        )
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Status update propagation
# ---------------------------------------------------------------------------


@runtime_checkable
class FirebaseWriter(Protocol):
    """Writes data to Firebase RTDB."""

    def write(self, path: str, data: Any) -> None: ...


@dataclass
class StatusUpdateResult:
    """Outcome of a responder status update."""

    unit_id: str
    previous_status: str
    new_status: str
    accepted: bool = False
    firebase_written: bool = False
    error: str | None = None


def propagate_status_update(
    unit_id: str,
    current_status: UnitStatus,
    new_status: UnitStatus,
    firebase: FirebaseWriter,
) -> StatusUpdateResult:
    """Validate and propagate a responder status update.

    Validates the transition against the allowed state machine
    (Req 7.4, 8.2), then writes to Firebase RTDB so the Operator
    Dashboard receives the update in < 200ms (Req 7.5).

    Parameters
    ----------
    unit_id : str
        The responder's unit identifier.
    current_status : UnitStatus
        The unit's current status.
    new_status : UnitStatus
        The requested new status.
    firebase : FirebaseWriter
        Firebase RTDB writer.

    Returns
    -------
    StatusUpdateResult
    """
    result = StatusUpdateResult(
        unit_id=unit_id,
        previous_status=current_status.value,
        new_status=new_status.value,
    )

    if not is_valid_transition(current_status, new_status):
        result.error = (
            f"Invalid transition: {current_status.value} → {new_status.value}"
        )
        return result

    result.accepted = True

    try:
        firebase.write(unit_status(unit_id), new_status.value)
        result.firebase_written = True
    except Exception as exc:
        logger.error(
            "Failed to write status update for unit %s: %s", unit_id, exc
        )
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# GPS location consumption
# ---------------------------------------------------------------------------

# Staleness threshold: if a GPS update is older than 60 seconds,
# the unit's location is considered stale (design doc error handling).
GPS_STALENESS_THRESHOLD_SECONDS = 60

# GPS update interval: the Responder App pushes location every 10 seconds
# (Req 7.6, 8.1).
GPS_UPDATE_INTERVAL_SECONDS = 10


@dataclass
class GPSUpdate:
    """A single GPS location update from a responder."""

    unit_id: str
    lat: float
    lng: float
    timestamp: float  # Unix timestamp
    is_stale: bool = False


def process_gps_update(
    unit_id: str,
    lat: float,
    lng: float,
    firebase: FirebaseWriter,
    timestamp: float | None = None,
) -> GPSUpdate:
    """Process a GPS location update from the Responder App.

    Writes the location to Firebase RTDB at ``/units/{unit_id}/location``
    so the Dispatch Engine can consume it for subsequent queries (Req 8.3).

    Parameters
    ----------
    unit_id : str
        The responder's unit identifier.
    lat : float
        Latitude.
    lng : float
        Longitude.
    firebase : FirebaseWriter
        Firebase RTDB writer.
    timestamp : float | None
        Unix timestamp of the update. Defaults to current time.

    Returns
    -------
    GPSUpdate
    """
    ts = timestamp or time.time()
    is_stale = (time.time() - ts) > GPS_STALENESS_THRESHOLD_SECONDS

    update = GPSUpdate(
        unit_id=unit_id,
        lat=lat,
        lng=lng,
        timestamp=ts,
        is_stale=is_stale,
    )

    try:
        firebase.write(
            unit_location(unit_id),
            {"lat": lat, "lng": lng, "last_updated": int(ts)},
        )
    except Exception as exc:
        logger.error(
            "Failed to write GPS update for unit %s: %s", unit_id, exc
        )

    return update
