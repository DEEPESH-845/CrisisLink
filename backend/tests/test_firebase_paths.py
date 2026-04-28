"""Unit tests for Firebase RTDB path helpers.

Requirements: 10.3, 8.4
"""

import pytest

from shared.firebase.paths import (
    all_units,
    call_caller_state,
    call_classification,
    call_confirmed_unit,
    call_dispatch_card,
    call_guidance,
    call_manual_override,
    call_started_at,
    call_transcript,
    call_updated_at,
    unit,
    unit_location,
    unit_status,
)


# ---------------------------------------------------------------------------
# Call-level path helpers
# ---------------------------------------------------------------------------


class TestCallPaths:
    """Verify each call-level path helper returns the correct RTDB path."""

    def test_call_transcript(self):
        assert call_transcript("CALL-001") == "/calls/CALL-001/transcript"

    def test_call_classification(self):
        assert call_classification("CALL-001") == "/calls/CALL-001/classification"

    def test_call_caller_state(self):
        assert call_caller_state("CALL-001") == "/calls/CALL-001/caller_state"

    def test_call_dispatch_card(self):
        assert call_dispatch_card("CALL-001") == "/calls/CALL-001/dispatch_card"

    def test_call_confirmed_unit(self):
        assert call_confirmed_unit("CALL-001") == "/calls/CALL-001/confirmed_unit"

    def test_call_guidance(self):
        assert call_guidance("CALL-001") == "/calls/CALL-001/guidance"

    def test_call_manual_override(self):
        assert call_manual_override("CALL-001") == "/calls/CALL-001/manual_override"

    def test_call_started_at(self):
        assert call_started_at("CALL-001") == "/calls/CALL-001/started_at"

    def test_call_updated_at(self):
        assert call_updated_at("CALL-001") == "/calls/CALL-001/updated_at"

    def test_call_paths_with_numeric_id(self):
        assert call_transcript("12345") == "/calls/12345/transcript"

    def test_call_paths_with_uuid_style_id(self):
        cid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert call_classification(cid) == f"/calls/{cid}/classification"


# ---------------------------------------------------------------------------
# Unit-level path helpers
# ---------------------------------------------------------------------------


class TestUnitPaths:
    """Verify each unit-level path helper returns the correct RTDB path."""

    def test_unit(self):
        assert unit("AMB_007") == "/units/AMB_007"

    def test_unit_status(self):
        assert unit_status("AMB_007") == "/units/AMB_007/status"

    def test_unit_location(self):
        assert unit_location("AMB_007") == "/units/AMB_007/location"

    def test_all_units(self):
        assert all_units() == "/units"

    def test_unit_with_different_id(self):
        assert unit("FB_003") == "/units/FB_003"
        assert unit_status("POL_012") == "/units/POL_012/status"
        assert unit_location("AMB_100") == "/units/AMB_100/location"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestPathValidation:
    """Verify that invalid IDs are rejected."""

    def test_empty_call_id_rejected(self):
        with pytest.raises(ValueError, match="call_id"):
            call_transcript("")

    def test_whitespace_call_id_rejected(self):
        with pytest.raises(ValueError, match="call_id"):
            call_transcript("   ")

    def test_slash_in_call_id_rejected(self):
        with pytest.raises(ValueError, match="call_id"):
            call_transcript("CALL/001")

    def test_empty_unit_id_rejected(self):
        with pytest.raises(ValueError, match="unit_id"):
            unit("")

    def test_whitespace_unit_id_rejected(self):
        with pytest.raises(ValueError, match="unit_id"):
            unit_status("   ")

    def test_slash_in_unit_id_rejected(self):
        with pytest.raises(ValueError, match="unit_id"):
            unit_location("AMB/007")


# ---------------------------------------------------------------------------
# Path structure invariants
# ---------------------------------------------------------------------------


class TestPathStructure:
    """Verify structural properties of all generated paths."""

    def test_all_call_paths_start_with_calls_prefix(self):
        call_helpers = [
            call_transcript,
            call_classification,
            call_caller_state,
            call_dispatch_card,
            call_confirmed_unit,
            call_guidance,
            call_manual_override,
            call_started_at,
            call_updated_at,
        ]
        for helper in call_helpers:
            path = helper("TEST")
            assert path.startswith("/calls/TEST/"), f"{helper.__name__} returned {path}"

    def test_all_unit_paths_start_with_units_prefix(self):
        assert unit("U1").startswith("/units/U1")
        assert unit_status("U1").startswith("/units/U1/")
        assert unit_location("U1").startswith("/units/U1/")

    def test_all_paths_are_absolute(self):
        """Every path must start with '/'."""
        all_helpers = [
            lambda: call_transcript("X"),
            lambda: call_classification("X"),
            lambda: call_caller_state("X"),
            lambda: call_dispatch_card("X"),
            lambda: call_confirmed_unit("X"),
            lambda: call_guidance("X"),
            lambda: call_manual_override("X"),
            lambda: call_started_at("X"),
            lambda: call_updated_at("X"),
            lambda: unit("X"),
            lambda: unit_status("X"),
            lambda: unit_location("X"),
            all_units,
        ]
        for fn in all_helpers:
            path = fn()
            assert path.startswith("/"), f"Path '{path}' is not absolute"
