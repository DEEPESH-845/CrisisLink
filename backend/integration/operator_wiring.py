"""Operator Dashboard ↔ Backend Wiring.

Documents and implements the wiring between the Operator Dashboard
(Flutter Web) and all backend services via Firebase RTDB.

Firebase RTDB paths consumed by the dashboard:
    /calls/{call_id}/transcript       — live transcript (Req 6.1, 6.2)
    /calls/{call_id}/classification   — streaming triage card (Req 6.2)
    /calls/{call_id}/caller_state     — caller state updates (Req 6.2)
    /calls/{call_id}/dispatch_card    — dispatch recommendations (Req 6.3)
    /calls/{call_id}/guidance         — guidance status (Req 6.5)

Dashboard actions:
    Dispatch confirmation → Dispatch Service confirm endpoint (Req 6.3, 6.4)
    Classification override → BigQuery audit log (Req 6.7, 10.4)

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from shared.firebase.paths import (
    call_classification,
    call_confirmed_unit,
    call_dispatch_card,
    call_guidance,
    call_transcript,
    unit_status,
)
from shared.models import AuditEventType, AuditLogEntry
from speech_ingestion.audit_logger import AuditEntry, AuditLogger, MockAuditLogger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Firebase RTDB path registry for the Operator Dashboard
# ---------------------------------------------------------------------------

OPERATOR_DASHBOARD_SUBSCRIPTIONS: dict[str, str] = {
    "transcript": "/calls/{call_id}/transcript",
    "classification": "/calls/{call_id}/classification",
    "caller_state": "/calls/{call_id}/caller_state",
    "dispatch_card": "/calls/{call_id}/dispatch_card",
    "guidance": "/calls/{call_id}/guidance",
}


def get_dashboard_paths(call_id: str) -> dict[str, str]:
    """Return the concrete Firebase RTDB paths for a given call.

    These are the paths the Operator Dashboard subscribes to for
    real-time updates.

    Parameters
    ----------
    call_id : str
        The active call session identifier.

    Returns
    -------
    dict[str, str]
        Mapping of data type → RTDB path.
    """
    return {
        "transcript": call_transcript(call_id),
        "classification": call_classification(call_id),
        "dispatch_card": call_dispatch_card(call_id),
        "guidance": call_guidance(call_id),
    }


# ---------------------------------------------------------------------------
# Dispatch confirmation flow
# ---------------------------------------------------------------------------


@runtime_checkable
class DispatchConfirmationHandler(Protocol):
    """Handles dispatch confirmation from the Operator Dashboard."""

    async def confirm(self, call_id: str, unit_id: str) -> dict[str, str]:
        """Confirm dispatch and return status dict."""
        ...


@runtime_checkable
class FirebaseWriter(Protocol):
    """Writes data to Firebase RTDB."""

    def write(self, path: str, data: Any) -> None: ...


@dataclass
class DispatchConfirmationResult:
    """Outcome of a dispatch confirmation from the dashboard."""

    call_id: str
    unit_id: str
    status: str = ""
    unit_status_updated: bool = False
    fcm_notification_sent: bool = False
    audit_logged: bool = False
    error: str | None = None


async def handle_dispatch_confirmation(
    call_id: str,
    unit_id: str,
    dispatch_handler: DispatchConfirmationHandler,
    firebase: FirebaseWriter,
    audit_logger: AuditLogger,
) -> DispatchConfirmationResult:
    """Process a dispatch confirmation from the Operator Dashboard.

    Flow:
    1. Call Dispatch Service confirm endpoint (updates unit status + FCM)
    2. Write confirmed_unit to Firebase RTDB
    3. Write audit log entry

    Parameters
    ----------
    call_id : str
        The call session being dispatched.
    unit_id : str
        The unit selected by the operator.
    dispatch_handler : DispatchConfirmationHandler
        The dispatch service confirm handler.
    firebase : FirebaseWriter
        Firebase RTDB writer.
    audit_logger : AuditLogger
        BigQuery audit logger.

    Returns
    -------
    DispatchConfirmationResult
    """
    result = DispatchConfirmationResult(call_id=call_id, unit_id=unit_id)

    try:
        # 1. Call dispatch confirm endpoint
        confirm_result = await dispatch_handler.confirm(call_id, unit_id)
        result.status = confirm_result.get("status", "dispatched")
        result.unit_status_updated = True
        result.fcm_notification_sent = True

        # 2. Write confirmed unit to Firebase RTDB
        firebase.write(
            call_confirmed_unit(call_id),
            unit_id,
        )

        # 3. Audit log
        entry = AuditEntry(
            call_id=call_id,
            event_type=AuditEventType.DISPATCH.value,
            timestamp=datetime.now(timezone.utc),
            payload={
                "unit_id": unit_id,
                "action": "operator_dispatch_confirmed",
            },
        )
        audit_logger.log(entry)
        result.audit_logged = True

    except Exception as exc:
        logger.error(
            "Dispatch confirmation failed for call %s, unit %s: %s",
            call_id, unit_id, exc,
        )
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Classification override audit logging
# ---------------------------------------------------------------------------


@dataclass
class ClassificationOverrideResult:
    """Outcome of a classification override by the operator."""

    call_id: str
    operator_id: str
    original_type: str
    override_type: str
    original_severity: str
    override_severity: str
    audit_logged: bool = False
    error: str | None = None


def log_classification_override(
    call_id: str,
    operator_id: str,
    original_type: str,
    override_type: str,
    original_severity: str,
    override_severity: str,
    audit_logger: AuditLogger,
) -> ClassificationOverrideResult:
    """Record a classification override to the BigQuery audit log.

    When an operator manually overrides the AI classification, this
    function writes an audit entry for compliance (Req 6.7, 10.4)
    and classification accuracy monitoring (Req 9.4, 9.6).

    Parameters
    ----------
    call_id : str
        The call session identifier.
    operator_id : str
        The operator who performed the override.
    original_type : str
        The AI-produced emergency type.
    override_type : str
        The operator-selected emergency type.
    original_severity : str
        The AI-produced severity.
    override_severity : str
        The operator-selected severity.
    audit_logger : AuditLogger
        BigQuery audit logger.

    Returns
    -------
    ClassificationOverrideResult
    """
    result = ClassificationOverrideResult(
        call_id=call_id,
        operator_id=operator_id,
        original_type=original_type,
        override_type=override_type,
        original_severity=original_severity,
        override_severity=override_severity,
    )

    try:
        entry = AuditEntry(
            call_id=call_id,
            event_type=AuditEventType.OPERATOR_OVERRIDE.value,
            timestamp=datetime.now(timezone.utc),
            payload={
                "operator_id": operator_id,
                "original_emergency_type": original_type,
                "override_emergency_type": override_type,
                "original_severity": original_severity,
                "override_severity": override_severity,
            },
        )
        audit_logger.log(entry)
        result.audit_logged = True

    except Exception as exc:
        logger.error(
            "Failed to log classification override for call %s: %s",
            call_id, exc,
        )
        result.error = str(exc)

    return result
