"""Firebase Realtime Database path construction utilities.

Provides helper functions for building canonical RTDB paths used across
CrisisLink backend services.  Every path returned is an absolute path
(leading ``/``) so it can be passed directly to the Firebase Admin SDK
``db.reference()`` call.

Requirements: 10.3, 8.4
"""


def _validate_id(value: str, name: str) -> None:
    """Raise ``ValueError`` when *value* is empty or contains path separators."""
    if not value or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if "/" in value:
        raise ValueError(f"{name} must not contain '/' characters")


# ---------------------------------------------------------------------------
# Call-level paths  –  /calls/{call_id}/…
# ---------------------------------------------------------------------------


def call_transcript(call_id: str) -> str:
    """Return the path to a call's rolling transcript."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/transcript"


def call_classification(call_id: str) -> str:
    """Return the path to a call's emergency classification."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/classification"


def call_caller_state(call_id: str) -> str:
    """Return the path to a call's caller state."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/caller_state"


def call_dispatch_card(call_id: str) -> str:
    """Return the path to a call's dispatch card."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/dispatch_card"


def call_confirmed_unit(call_id: str) -> str:
    """Return the path to a call's confirmed (dispatched) unit."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/confirmed_unit"


def call_guidance(call_id: str) -> str:
    """Return the path to a call's guidance data."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/guidance"


def call_manual_override(call_id: str) -> str:
    """Return the path to a call's manual-override flag."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/manual_override"


def call_started_at(call_id: str) -> str:
    """Return the path to a call's started_at timestamp."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/started_at"


def call_updated_at(call_id: str) -> str:
    """Return the path to a call's updated_at timestamp."""
    _validate_id(call_id, "call_id")
    return f"/calls/{call_id}/updated_at"


# ---------------------------------------------------------------------------
# Unit-level paths  –  /units/{unit_id}/…
# ---------------------------------------------------------------------------


def unit(unit_id: str) -> str:
    """Return the path to a specific response unit."""
    _validate_id(unit_id, "unit_id")
    return f"/units/{unit_id}"


def unit_status(unit_id: str) -> str:
    """Return the path to a unit's status field."""
    _validate_id(unit_id, "unit_id")
    return f"/units/{unit_id}/status"


def unit_location(unit_id: str) -> str:
    """Return the path to a unit's location object."""
    _validate_id(unit_id, "unit_id")
    return f"/units/{unit_id}/location"


def all_units() -> str:
    """Return the path to the top-level units collection."""
    return "/units"
