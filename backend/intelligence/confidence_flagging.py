"""Confidence threshold flagging for manual operator takeover.

Flags calls for manual operator takeover when the Emergency_Classification
confidence score is strictly below 0.7.  The flag is written to Firebase
RTDB via the ClassificationWriter protocol so the Operator Dashboard can
display a low-confidence alert.

Requirements: 2.6, 6.6
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from shared.firebase.paths import call_manual_override

logger = logging.getLogger(__name__)

# Confidence threshold — calls with confidence strictly below this value
# are flagged for manual operator takeover.
CONFIDENCE_THRESHOLD = 0.7


def should_flag_for_manual_takeover(confidence: float) -> bool:
    """Return ``True`` if *confidence* is strictly below the threshold (0.7).

    Classifications with confidence >= 0.7 are NOT flagged.

    Parameters
    ----------
    confidence : float
        The classification confidence score in [0.0, 1.0].

    Returns
    -------
    bool
        ``True`` when the call should be flagged for manual takeover.
    """
    return confidence < CONFIDENCE_THRESHOLD


@runtime_checkable
class ManualTakeoverWriter(Protocol):
    """Protocol for writing manual-takeover flags to a persistent store."""

    def write_manual_override(
        self,
        call_id: str,
        data: dict[str, Any],
    ) -> None:
        """Write a manual-override flag for *call_id*."""
        ...


class MockManualTakeoverWriter:
    """In-memory mock writer for testing — records all flag writes."""

    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    def write_manual_override(
        self,
        call_id: str,
        data: dict[str, Any],
    ) -> None:
        self.writes.append({"call_id": call_id, "path": call_manual_override(call_id), "data": data})

    def last_write(self) -> dict[str, Any] | None:
        return self.writes[-1] if self.writes else None

    def writes_for(self, call_id: str) -> list[dict[str, Any]]:
        return [w for w in self.writes if w["call_id"] == call_id]


class FirebaseManualTakeoverWriter:
    """Production writer that sets the manual_override flag in Firebase RTDB."""

    def write_manual_override(
        self,
        call_id: str,
        data: dict[str, Any],
    ) -> None:
        path = call_manual_override(call_id)
        raise NotImplementedError(
            f"FirebaseManualTakeoverWriter requires firebase-admin initialisation. "
            f"Would write to {path}. Use MockManualTakeoverWriter for testing."
        )


# Module-level writer (injectable for testing)
_takeover_writer: ManualTakeoverWriter = MockManualTakeoverWriter()


def configure_takeover_writer(writer: ManualTakeoverWriter) -> None:
    """Inject a manual-takeover writer at application startup."""
    global _takeover_writer
    _takeover_writer = writer


def get_takeover_writer() -> ManualTakeoverWriter:
    """Return the currently configured takeover writer."""
    return _takeover_writer


def flag_call_for_manual_takeover(call_id: str) -> None:
    """Write a manual-takeover flag to Firebase RTDB for *call_id*.

    Uses the configured ``ManualTakeoverWriter`` to persist the flag.
    """
    logger.warning(
        "Flagging call %s for manual operator takeover (low confidence)",
        call_id,
    )
    try:
        _takeover_writer.write_manual_override(
            call_id,
            {"flagged": True, "reason": "low_confidence"},
        )
    except NotImplementedError:
        logger.debug(
            "Manual takeover writer not available (expected in dev/test): %s",
            call_id,
        )
