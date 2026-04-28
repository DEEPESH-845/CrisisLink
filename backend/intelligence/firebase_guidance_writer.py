"""Firebase Realtime Database writer for guidance data.

Defines a ``GuidanceWriter`` protocol and implementations for writing
guidance status, language, and protocol type to Firebase RTDB at
``/calls/{call_id}/guidance``.

Mirrors the ``ClassificationWriter`` pattern from the Intelligence Service.

Requirements: 5.1, 5.2, 5.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from shared.firebase.paths import call_guidance

logger = logging.getLogger(__name__)


@runtime_checkable
class GuidanceWriter(Protocol):
    """Protocol for writing guidance data to a persistent store."""

    def write_guidance(
        self,
        call_id: str,
        guidance_data: dict[str, Any],
    ) -> None:
        """Write or update the guidance data for *call_id*.

        Parameters
        ----------
        call_id : str
            Unique call session identifier.
        guidance_data : dict
            Guidance data containing status, language, protocol_type,
            and optionally the guidance text.
        """
        ...


class MockGuidanceWriter:
    """In-memory mock writer for testing — records all guidance writes."""

    @dataclass
    class WriteRecord:
        """A single recorded guidance write operation."""

        call_id: str
        path: str
        data: dict[str, Any]

    def __init__(self) -> None:
        self.writes: list[MockGuidanceWriter.WriteRecord] = []

    def write_guidance(
        self,
        call_id: str,
        guidance_data: dict[str, Any],
    ) -> None:
        """Record the guidance write for later assertion in tests."""
        path = call_guidance(call_id)
        self.writes.append(
            self.WriteRecord(
                call_id=call_id,
                path=path,
                data=guidance_data,
            )
        )

    def last_write(self) -> WriteRecord | None:
        """Return the most recent guidance write, or ``None``."""
        return self.writes[-1] if self.writes else None

    def writes_for(self, call_id: str) -> list[WriteRecord]:
        """Return all guidance writes for a specific *call_id*."""
        return [w for w in self.writes if w.call_id == call_id]


class FirebaseGuidanceWriter:
    """Production writer that pushes guidance data to Firebase RTDB.

    Requires ``firebase_admin`` to be initialised before use.
    """

    def write_guidance(
        self,
        call_id: str,
        guidance_data: dict[str, Any],
    ) -> None:
        """Write the guidance payload to Firebase RTDB.

        Raises ``NotImplementedError`` until firebase-admin is initialised
        in the deployment environment.
        """
        path = call_guidance(call_id)
        raise NotImplementedError(
            f"FirebaseGuidanceWriter requires firebase-admin initialisation. "
            f"Would write to {path}. Use MockGuidanceWriter for testing."
        )


# ---------------------------------------------------------------------------
# Module-level writer (injectable for testing)
# ---------------------------------------------------------------------------

_guidance_writer: GuidanceWriter = MockGuidanceWriter()


def configure_guidance_writer(writer: GuidanceWriter) -> None:
    """Inject a guidance writer at application startup."""
    global _guidance_writer
    _guidance_writer = writer


def get_guidance_writer() -> GuidanceWriter:
    """Return the currently configured guidance writer."""
    return _guidance_writer


def write_guidance_to_firebase(
    call_id: str,
    status: str,
    language: str,
    protocol_type: str,
    guidance_text: str = "",
) -> None:
    """Write guidance data to Firebase RTDB at ``/calls/{call_id}/guidance``.

    Parameters
    ----------
    call_id : str
        Unique call session identifier.
    status : str
        Guidance status: generating, active, completed, not_applicable.
    language : str
        ISO 639-1 language code of the guidance.
    protocol_type : str
        Protocol identifier (e.g., CPR_IRC_2022, FIRE_NDMA, GENERAL).
    guidance_text : str
        The generated guidance text (optional).
    """
    guidance_data: dict[str, Any] = {
        "status": status,
        "language": language,
        "protocol_type": protocol_type,
    }
    if guidance_text:
        guidance_data["text"] = guidance_text

    try:
        _guidance_writer.write_guidance(call_id, guidance_data)
    except NotImplementedError:
        logger.debug(
            "Guidance writer not available (expected in dev/test): %s",
            call_id,
        )
