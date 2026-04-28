"""Business logic for audio chunk processing in the Speech Ingestion Service.

This module provides an in-memory store for audio chunks and transcript state.
The actual Whisper / Google STT transcription pipeline will be wired in task 3.2.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class CallTranscriptState:
    """In-memory state for a single call's audio processing."""

    call_id: str
    transcript: str = ""
    language_detected: str = "unknown"
    chunks_processed: int = 0
    audio_chunks: list[bytes] = field(default_factory=list)


class SpeechIngestionStore:
    """Thread-safe in-memory store for call audio chunks and transcripts.

    This is a stub implementation that accumulates chunks and tracks counts.
    The real transcription pipeline (Whisper Large-v3 / Google STT v2 fallback)
    will be integrated in task 3.2.
    """

    def __init__(self) -> None:
        self._calls: dict[str, CallTranscriptState] = {}
        self._lock = threading.Lock()

    def ingest_chunk(self, call_id: str, audio_data: bytes) -> CallTranscriptState:
        """Store an audio chunk for *call_id* and return the updated state."""
        with self._lock:
            state = self._calls.get(call_id)
            if state is None:
                state = CallTranscriptState(call_id=call_id)
                self._calls[call_id] = state
            state.audio_chunks.append(audio_data)
            state.chunks_processed += 1
            return state

    def get_state(self, call_id: str) -> CallTranscriptState | None:
        """Return the current transcript state for *call_id*, or ``None``."""
        with self._lock:
            return self._calls.get(call_id)

    def reset(self) -> None:
        """Clear all stored state (useful for testing)."""
        with self._lock:
            self._calls.clear()
