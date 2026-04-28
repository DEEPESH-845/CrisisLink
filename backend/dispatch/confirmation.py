"""Dispatch confirmation flow.

Handles:
- Updating Response_Unit status to "dispatched" in Firebase RTDB
- Sending push notification to field responder via FCM
- Writing dispatch audit log entry to BigQuery

Requirements: 4.5, 10.4
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from shared.models import AuditEventType, AuditLogEntry

logger = logging.getLogger(__name__)


class FCMClient(Protocol):
    """Protocol for sending Firebase Cloud Messaging notifications."""

    async def send_dispatch_notification(
        self, unit_id: str, call_id: str, payload: dict[str, Any]
    ) -> bool:
        """Send a dispatch push notification to the responder's device.

        Returns True on success, False on failure.
        """
        ...


class AuditLogger(Protocol):
    """Protocol for writing audit log entries to BigQuery."""

    async def write_entry(self, entry: AuditLogEntry) -> None:
        """Write an audit log entry."""
        ...


class MockFCMClient:
    """Mock FCM client that records sent notifications for testing."""

    def __init__(self) -> None:
        self.sent_notifications: list[dict[str, Any]] = []

    async def send_dispatch_notification(
        self, unit_id: str, call_id: str, payload: dict[str, Any]
    ) -> bool:
        self.sent_notifications.append(
            {"unit_id": unit_id, "call_id": call_id, "payload": payload}
        )
        logger.info("Mock FCM: sent dispatch notification to %s for call %s", unit_id, call_id)
        return True


class MockAuditLogger:
    """Mock audit logger that records entries in memory for testing."""

    def __init__(self) -> None:
        self.entries: list[AuditLogEntry] = []

    async def write_entry(self, entry: AuditLogEntry) -> None:
        self.entries.append(entry)
        logger.info("Mock audit: logged %s for call %s", entry.event_type, entry.call_id)


async def confirm_dispatch(
    call_id: str,
    unit_id: str,
    unit_store: Any,
    fcm_client: FCMClient,
    audit_logger: AuditLogger,
) -> dict[str, str]:
    """Execute the dispatch confirmation flow.

    1. Update the unit's status to "dispatched" in the data store.
    2. Send a push notification to the field responder via FCM.
    3. Write a dispatch audit log entry to BigQuery.

    Returns a dict with ``status`` and ``unit_id`` keys.
    """
    # 1. Update unit status
    await unit_store.update_unit_status(unit_id, "dispatched")
    logger.info("Unit %s status updated to dispatched for call %s", unit_id, call_id)

    # 2. Send FCM push notification
    notification_payload = {
        "call_id": call_id,
        "unit_id": unit_id,
        "action": "dispatch",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    success = await fcm_client.send_dispatch_notification(
        unit_id=unit_id, call_id=call_id, payload=notification_payload
    )
    if not success:
        logger.warning(
            "FCM notification failed for unit %s on call %s", unit_id, call_id
        )

    # 3. Write audit log entry
    audit_entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        call_id=call_id,
        event_type=AuditEventType.DISPATCH,
        payload={
            "unit_id": unit_id,
            "action": "dispatch_confirmed",
        },
        actor="dispatch-service",
        timestamp=datetime.now(timezone.utc),
    )
    await audit_logger.write_entry(audit_entry)

    return {"status": "dispatched", "unit_id": unit_id}
