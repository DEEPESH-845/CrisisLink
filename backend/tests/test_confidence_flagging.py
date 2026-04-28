"""Tests for confidence threshold flagging logic.

Verifies that calls are flagged for manual operator takeover when the
classification confidence is strictly below 0.7, and NOT flagged when
confidence is >= 0.7.

Requirements: 2.6, 6.6
"""

import pytest

from intelligence.confidence_flagging import (
    CONFIDENCE_THRESHOLD,
    MockManualTakeoverWriter,
    configure_takeover_writer,
    flag_call_for_manual_takeover,
    get_takeover_writer,
    should_flag_for_manual_takeover,
)


class TestShouldFlagForManualTakeover:
    """Unit tests for the should_flag_for_manual_takeover function."""

    def test_confidence_below_threshold_is_flagged(self):
        """Confidence 0.69 → flagged."""
        assert should_flag_for_manual_takeover(0.69) is True

    def test_confidence_at_threshold_is_not_flagged(self):
        """Confidence 0.70 → NOT flagged (boundary)."""
        assert should_flag_for_manual_takeover(0.70) is False

    def test_confidence_zero_is_flagged(self):
        """Confidence 0.0 → flagged."""
        assert should_flag_for_manual_takeover(0.0) is True

    def test_confidence_one_is_not_flagged(self):
        """Confidence 1.0 → NOT flagged."""
        assert should_flag_for_manual_takeover(1.0) is False

    def test_confidence_exactly_at_boundary(self):
        """Confidence exactly 0.7 → NOT flagged (strictly below triggers)."""
        assert should_flag_for_manual_takeover(0.7) is False

    def test_confidence_just_below_boundary(self):
        """Confidence 0.6999... → flagged."""
        assert should_flag_for_manual_takeover(0.6999999) is True

    def test_confidence_just_above_boundary(self):
        """Confidence 0.7000001 → NOT flagged."""
        assert should_flag_for_manual_takeover(0.7000001) is False

    def test_threshold_constant_is_0_7(self):
        """Verify the threshold constant is 0.7."""
        assert CONFIDENCE_THRESHOLD == 0.7


class TestFlagCallForManualTakeover:
    """Tests for the flag_call_for_manual_takeover function with mock writer."""

    @pytest.fixture(autouse=True)
    def _setup_mock_writer(self):
        """Install a fresh mock writer before each test."""
        writer = MockManualTakeoverWriter()
        configure_takeover_writer(writer)
        yield
        # Reset to a fresh mock after test
        configure_takeover_writer(MockManualTakeoverWriter())

    def test_flag_writes_to_mock_writer(self):
        """Flagging a call should record a write in the mock writer."""
        flag_call_for_manual_takeover("CALL-LOW-CONF")
        writer = get_takeover_writer()
        assert isinstance(writer, MockManualTakeoverWriter)
        assert len(writer.writes) == 1
        assert writer.writes[0]["call_id"] == "CALL-LOW-CONF"

    def test_flag_write_contains_reason(self):
        """The flag write should include the low_confidence reason."""
        flag_call_for_manual_takeover("CALL-001")
        writer = get_takeover_writer()
        assert isinstance(writer, MockManualTakeoverWriter)
        data = writer.writes[0]["data"]
        assert data["flagged"] is True
        assert data["reason"] == "low_confidence"

    def test_flag_write_uses_correct_firebase_path(self):
        """The flag write should target the correct Firebase RTDB path."""
        flag_call_for_manual_takeover("CALL-PATH")
        writer = get_takeover_writer()
        assert isinstance(writer, MockManualTakeoverWriter)
        assert writer.writes[0]["path"] == "/calls/CALL-PATH/manual_override"

    def test_multiple_flags_recorded_independently(self):
        """Multiple flag calls should each produce a separate write."""
        flag_call_for_manual_takeover("CALL-A")
        flag_call_for_manual_takeover("CALL-B")
        writer = get_takeover_writer()
        assert isinstance(writer, MockManualTakeoverWriter)
        assert len(writer.writes) == 2
        assert writer.writes_for("CALL-A") == [writer.writes[0]]
        assert writer.writes_for("CALL-B") == [writer.writes[1]]
