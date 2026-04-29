"""Property-based test for subsystem error notification.

Feature: crisislink-emergency-ai-copilot, Property 14: Subsystem Error Notification

Validates: Requirements 11.6

Uses Hypothesis to generate random subsystem failure scenarios and verify:
unrecoverable error in any subsystem → operator notified AND manual
call-handling preserved; no silent degradation.

The four CrisisLink subsystems:
    - Speech_Ingestion_Layer
    - Intelligence_Engine
    - Dispatch_Engine
    - TTS_Layer

Property statement:
    For any unrecoverable error in any subsystem during an active call,
    the Operator Dashboard SHALL notify the operator of the failure and
    the system SHALL preserve full manual call-handling capability.
    No subsystem failure SHALL silently degrade without operator notification.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from integration.subsystem_error_notification import (
    ALL_SUBSYSTEMS,
    Subsystem,
    SubsystemErrorNotificationResult,
    check_subsystem_error_notification,
    notify_subsystem_error,
)


# ---------------------------------------------------------------------------
# Mock Firebase writer for testing
# ---------------------------------------------------------------------------


class MockFirebaseAlertWriter:
    """Mock Firebase RTDB writer that records all writes."""

    def __init__(self) -> None:
        self.writes: dict[str, Any] = {}

    def write(self, path: str, data: Any) -> None:
        self.writes[path] = data


class MockAuditLogger:
    """Mock audit logger that records entries."""

    def __init__(self) -> None:
        self.entries: list[Any] = []

    def log(self, entry: Any) -> None:
        self.entries.append(entry)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for generating a random subsystem
subsystem_strategy = st.sampled_from(list(Subsystem))

# Strategy for generating a random call ID (non-empty string)
call_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=50,
)

# Strategy for generating a random error message (non-empty string)
error_message_strategy = st.text(min_size=1, max_size=200)


# ---------------------------------------------------------------------------
# Property 14: Subsystem Error Notification
# ---------------------------------------------------------------------------


class TestSubsystemErrorNotification:
    """Property 14: Subsystem Error Notification

    For any unrecoverable error in any subsystem (Speech_Ingestion_Layer,
    Intelligence_Engine, Dispatch_Engine, or TTS_Layer) during an active
    call, the Operator Dashboard SHALL notify the operator of the failure
    and the system SHALL preserve full manual call-handling capability.
    No subsystem failure SHALL silently degrade without operator notification.

    **Validates: Requirements 11.6**
    """

    @given(
        subsystem=subsystem_strategy,
        call_id=call_id_strategy,
        error_message=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_any_subsystem_error_notifies_operator(
        self,
        subsystem: Subsystem,
        call_id: str,
        error_message: str,
    ):
        """For any subsystem failure, the operator SHALL be notified.

        **Validates: Requirements 11.6**
        """
        firebase = MockFirebaseAlertWriter()
        audit = MockAuditLogger()

        result = notify_subsystem_error(
            call_id=call_id,
            subsystem=subsystem,
            error_message=error_message,
            firebase=firebase,
            audit_logger=audit,
        )

        assert result.operator_notified is True, (
            f"Operator was NOT notified for {subsystem.value} error "
            f"on call {call_id!r} — silent degradation detected"
        )

    @given(
        subsystem=subsystem_strategy,
        call_id=call_id_strategy,
        error_message=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_any_subsystem_error_preserves_manual_handling(
        self,
        subsystem: Subsystem,
        call_id: str,
        error_message: str,
    ):
        """For any subsystem failure, manual call-handling SHALL be preserved.

        **Validates: Requirements 11.6**
        """
        firebase = MockFirebaseAlertWriter()
        audit = MockAuditLogger()

        result = notify_subsystem_error(
            call_id=call_id,
            subsystem=subsystem,
            error_message=error_message,
            firebase=firebase,
            audit_logger=audit,
        )

        assert result.manual_handling_preserved is True, (
            f"Manual call-handling NOT preserved for {subsystem.value} error "
            f"on call {call_id!r}"
        )

    @given(
        subsystem=subsystem_strategy,
        call_id=call_id_strategy,
        error_message=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_no_silent_degradation(
        self,
        subsystem: Subsystem,
        call_id: str,
        error_message: str,
    ):
        """No subsystem failure SHALL silently degrade without notification.

        The combined check ensures both operator notification AND manual
        handling preservation — the two conditions that prevent silent
        degradation.

        **Validates: Requirements 11.6**
        """
        firebase = MockFirebaseAlertWriter()
        audit = MockAuditLogger()

        result = notify_subsystem_error(
            call_id=call_id,
            subsystem=subsystem,
            error_message=error_message,
            firebase=firebase,
            audit_logger=audit,
        )

        assert check_subsystem_error_notification(result) is True, (
            f"Silent degradation detected for {subsystem.value} error "
            f"on call {call_id!r}: operator_notified={result.operator_notified}, "
            f"manual_handling_preserved={result.manual_handling_preserved}"
        )

    @given(
        subsystem=subsystem_strategy,
        call_id=call_id_strategy,
        error_message=error_message_strategy,
    )
    @settings(max_examples=200)
    def test_firebase_alert_written_for_any_subsystem_error(
        self,
        subsystem: Subsystem,
        call_id: str,
        error_message: str,
    ):
        """A Firebase RTDB alert SHALL be written for any subsystem error.

        This verifies the Operator Dashboard receives the notification
        data via Firebase RTDB, including the subsystem identifier and
        error details.

        **Validates: Requirements 11.6**
        """
        firebase = MockFirebaseAlertWriter()
        audit = MockAuditLogger()

        result = notify_subsystem_error(
            call_id=call_id,
            subsystem=subsystem,
            error_message=error_message,
            firebase=firebase,
            audit_logger=audit,
        )

        # Verify alert was written to the correct Firebase path
        alert_path = f"/calls/{call_id}/alerts/subsystem_error"
        assert alert_path in firebase.writes, (
            f"No Firebase alert written at {alert_path} for "
            f"{subsystem.value} error"
        )

        alert_data = firebase.writes[alert_path]
        assert alert_data["subsystem"] == subsystem.value, (
            f"Alert subsystem mismatch: expected {subsystem.value}, "
            f"got {alert_data['subsystem']}"
        )
        assert alert_data["type"] == "subsystem_error"
        assert alert_data["manual_handling_required"] is True

        # Verify manual_override flag was set
        override_path = f"/calls/{call_id}/manual_override"
        assert override_path in firebase.writes, (
            f"manual_override flag not set at {override_path}"
        )
        assert firebase.writes[override_path] is True

    def test_all_four_subsystems_are_covered(self):
        """All four CrisisLink subsystems are represented in the enum.

        **Validates: Requirements 11.6**
        """
        expected = {
            "Speech_Ingestion_Layer",
            "Intelligence_Engine",
            "Dispatch_Engine",
            "TTS_Layer",
        }
        actual = {s.value for s in ALL_SUBSYSTEMS}
        assert actual == expected, (
            f"Subsystem coverage mismatch: expected {expected}, got {actual}"
        )
