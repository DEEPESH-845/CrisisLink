"""Subsystem Error Notification for Operator Dashboard.

Implements the error notification logic required by Requirement 11.6:

    IF any subsystem (Speech_Ingestion_Layer, Intelligence_Engine,
    Dispatch_Engine, or TTS_Layer) encounters an unrecoverable error
    during a call, THEN the Operator Dashboard SHALL notify the operator
    and preserve full manual call-handling capability.

The four CrisisLink subsystems:
    - Speech_Ingestion_Layer
    - Intelligence_Engine
    - Dispatch_Engine
    - TTS_Layer

For any unrecoverable error in any of these subsystems during an active
call, this module ensures:
    1. The operator is notified via Firebase RTDB alert
    2. Manual call-handling capability is preserved
    3. No subsystem failure silently degrades without notification

Requirements: 11.6
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subsystem identifiers
# ---------------------------------------------------------------------------


class Subsystem(str, Enum):
    """Identifies each CrisisLink subsystem that can fail."""

    SPEECH_INGESTION_LAYER = "Speech_Ingestion_Layer"
    INTELLIGENCE_ENGINE = "Intelligence_Engine"
    DISPATCH_ENGINE = "Dispatch_Engine"
    TTS_LAYER = "TTS_Layer"


# All valid subsystem identifiers
ALL_SUBSYSTEMS = frozenset(Subsystem)


# ---------------------------------------------------------------------------
# Notification result
# ---------------------------------------------------------------------------


@dataclass
class SubsystemErrorNotificationResult:
    """Outcome of a subsystem error notification attempt."""

    call_id: str
    subsystem: Subsystem
    error_message: str
    operator_notified: bool = False
    manual_handling_preserved: bool = False
    firebase_alert_written: bool = False
    audit_logged: bool = False
    notification_error: str | None = None


# ---------------------------------------------------------------------------
# Protocols for dependencies
# ---------------------------------------------------------------------------


@runtime_checkable
class FirebaseAlertWriter(Protocol):
    """Writes alert data to Firebase RTDB."""

    def write(self, path: str, data: Any) -> None: ...


@runtime_checkable
class AuditLogger(Protocol):
    """Logs audit entries."""

    def log(self, entry: Any) -> None: ...


# ---------------------------------------------------------------------------
# Core notification logic
# ---------------------------------------------------------------------------


def notify_subsystem_error(
    call_id: str,
    subsystem: Subsystem,
    error_message: str,
    firebase: FirebaseAlertWriter,
    audit_logger: AuditLogger | None = None,
) -> SubsystemErrorNotificationResult:
    """Notify the operator of an unrecoverable subsystem error.

    This function implements Requirement 11.6 by:
    1. Writing an alert to Firebase RTDB so the Operator Dashboard
       displays the failure notification.
    2. Preserving manual call-handling capability by setting the
       manual_override flag on the call session.
    3. Logging the error to the audit trail.

    Parameters
    ----------
    call_id : str
        The active call session identifier.
    subsystem : Subsystem
        The subsystem that encountered the unrecoverable error.
    error_message : str
        Description of the error.
    firebase : FirebaseAlertWriter
        Firebase RTDB writer for alert data.
    audit_logger : AuditLogger | None
        Optional audit logger for compliance logging.

    Returns
    -------
    SubsystemErrorNotificationResult
        Outcome of the notification attempt.
    """
    result = SubsystemErrorNotificationResult(
        call_id=call_id,
        subsystem=subsystem,
        error_message=error_message,
    )

    try:
        # 1. Write subsystem error alert to Firebase RTDB for the
        #    Operator Dashboard to display.
        alert_data = {
            "type": "subsystem_error",
            "subsystem": subsystem.value,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "manual_handling_required": True,
        }
        firebase.write(
            f"/calls/{call_id}/alerts/subsystem_error",
            alert_data,
        )
        result.firebase_alert_written = True
        result.operator_notified = True

        # 2. Preserve manual call-handling by setting manual_override flag.
        #    This ensures the operator can continue handling the call
        #    without AI assistance from the failed subsystem.
        firebase.write(
            f"/calls/{call_id}/manual_override",
            True,
        )
        result.manual_handling_preserved = True

        # 3. Audit log the error event
        if audit_logger is not None:
            try:
                from speech_ingestion.audit_logger import AuditEntry

                entry = AuditEntry(
                    call_id=call_id,
                    event_type="error",
                    timestamp=datetime.now(timezone.utc),
                    payload={
                        "subsystem": subsystem.value,
                        "error_message": error_message,
                        "action": "operator_notified",
                    },
                )
                audit_logger.log(entry)
                result.audit_logged = True
            except Exception as audit_exc:
                logger.warning(
                    "Audit logging failed for subsystem error on call %s: %s",
                    call_id,
                    audit_exc,
                )

    except Exception as exc:
        logger.error(
            "Failed to notify operator of %s error on call %s: %s",
            subsystem.value,
            call_id,
            exc,
        )
        result.notification_error = str(exc)

    return result


def check_subsystem_error_notification(
    result: SubsystemErrorNotificationResult,
) -> bool:
    """Check whether a subsystem error notification was successful.

    A notification is considered successful when:
    - The operator was notified (firebase alert written)
    - Manual call-handling capability is preserved

    No silent degradation is allowed — both conditions must be met.

    Returns
    -------
    bool
        True if the notification was fully successful.
    """
    return result.operator_notified and result.manual_handling_preserved
