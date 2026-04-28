"""Firebase Realtime Database writer for partial transcripts.

Defines a ``TranscriptWriter`` protocol and implementations for writing
rolling transcripts to ``/calls/{call_id}/transcript`` in Firebase RTDB.

Requirements: 1.2, 1.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from shared.firebase.paths import call_transcript


@runtime_checkable
class TranscriptWriter(Protocol):
    """Protocol for writing partial transcripts to a persistent store."""

    def write_transcript(
        self,
        call_id: str,
        transcript: str,
        language_detected: str,
        chunks_processed: int,
    ) -> None:
        """Write or update the rolling transcript for *call_id*.

        Parameters
        ----------
        call_id : str
            Unique call session identifier.
        transcript : str
            The accumulated transcript text so far.
        language_detected : str
            ISO 639-1 language code detected from the audio.
        chunks_processed : int
            Total number of audio chunks processed for this call.
        """
        ...


class MockTranscriptWriter:
    """In-memory mock writer for testing — records all writes."""

    @dataclass
    class WriteRecord:
        """A single recorded write operation."""

        call_id: str
        path: str
        transcript: str
        language_detected: str
        chunks_processed: int

    def __init__(self) -> None:
        self.writes: list[MockTranscriptWriter.WriteRecord] = []

    def write_transcript(
        self,
        call_id: str,
        transcript: str,
        language_detected: str,
        chunks_processed: int,
    ) -> None:
        """Record the write for later assertion in tests."""
        path = call_transcript(call_id)
        self.writes.append(
            self.WriteRecord(
                call_id=call_id,
                path=path,
                transcript=transcript,
                language_detected=language_detected,
                chunks_processed=chunks_processed,
            )
        )

    def last_write(self) -> WriteRecord | None:
        """Return the most recent write, or ``None``."""
        return self.writes[-1] if self.writes else None

    def writes_for(self, call_id: str) -> list[WriteRecord]:
        """Return all writes for a specific *call_id*."""
        return [w for w in self.writes if w.call_id == call_id]


class FirebaseTranscriptWriter:
    """Production writer that pushes transcripts to Firebase RTDB.

    Requires ``firebase_admin`` to be initialised before use.  This is a
    placeholder — the real implementation calls
    ``db.reference(path).set(payload)``.
    """

    def write_transcript(
        self,
        call_id: str,
        transcript: str,
        language_detected: str,
        chunks_processed: int,
    ) -> None:
        """Write the transcript payload to Firebase RTDB.

        Raises ``NotImplementedError`` until firebase-admin is initialised
        in the deployment environment.
        """
        path = call_transcript(call_id)
        _payload = {
            "text": transcript,
            "language_detected": language_detected,
            "chunks_processed": chunks_processed,
        }
        raise NotImplementedError(
            f"FirebaseTranscriptWriter requires firebase-admin initialisation. "
            f"Would write to {path}. Use MockTranscriptWriter for testing."
        )
