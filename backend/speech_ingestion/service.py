"""Business logic for audio chunk processing in the Speech Ingestion Service.

This module provides the ``SpeechIngestionStore`` which orchestrates the
audio chunking → transcription → Firebase write pipeline.

The store accepts dependency-injected ``Transcriber`` and ``TranscriptWriter``
instances so that tests can supply mocks while production uses the real
Whisper Large-v3 model and Firebase RTDB writer.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .chunker import AudioChunker
from .firebase_writer import TranscriptWriter
from .transcriber import Transcriber


@dataclass
class CallTranscriptState:
    """In-memory state for a single call's audio processing."""

    call_id: str
    transcript: str = ""
    language_detected: str = "unknown"
    chunks_processed: int = 0
    audio_chunks: list[bytes] = field(default_factory=list)
    chunker: AudioChunker = field(default_factory=AudioChunker)


class SpeechIngestionStore:
    """Thread-safe store that orchestrates the speech ingestion pipeline.

    Pipeline per call:
    1. Incoming audio bytes are fed to an :class:`AudioChunker`.
    2. Each complete 500ms chunk is passed to the :class:`Transcriber`.
    3. The rolling transcript and detected language are updated.
    4. The :class:`TranscriptWriter` pushes the partial transcript to
       Firebase RTDB at ``/calls/{call_id}/transcript``.

    Parameters
    ----------
    transcriber : Transcriber | None
        Speech-to-text backend.  When ``None`` the store still accumulates
        chunks and counts but does not produce transcripts (backwards-
        compatible with the task 3.1 stub behaviour).
    writer : TranscriptWriter | None
        Persistent store writer.  When ``None`` transcripts are kept only
        in memory.
    """

    def __init__(
        self,
        transcriber: Transcriber | None = None,
        writer: TranscriptWriter | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._writer = writer
        self._calls: dict[str, CallTranscriptState] = {}
        self._lock = threading.Lock()

    def ingest_chunk(self, call_id: str, audio_data: bytes) -> CallTranscriptState:
        """Process an incoming audio chunk for *call_id*.

        The audio is buffered by the chunker.  For each complete 500ms
        segment the transcriber is invoked and the rolling transcript is
        updated.  If a writer is configured the partial transcript is
        also pushed to Firebase RTDB.

        Returns the updated :class:`CallTranscriptState`.
        """
        with self._lock:
            state = self._calls.get(call_id)
            if state is None:
                state = CallTranscriptState(call_id=call_id)
                self._calls[call_id] = state

            # Feed audio into the chunker
            complete_chunks = state.chunker.add_audio(audio_data)

            for chunk in complete_chunks:
                state.audio_chunks.append(chunk)
                state.chunks_processed += 1

                # Run transcription if a transcriber is available
                if self._transcriber is not None:
                    result = self._transcriber.transcribe(chunk)
                    # Append to rolling transcript (space-separated segments)
                    if state.transcript:
                        state.transcript += " " + result.text
                    else:
                        state.transcript = result.text
                    state.language_detected = result.language

                    # Push partial transcript to Firebase RTDB
                    if self._writer is not None:
                        self._writer.write_transcript(
                            call_id=call_id,
                            transcript=state.transcript,
                            language_detected=state.language_detected,
                            chunks_processed=state.chunks_processed,
                        )

            # If no complete chunks were produced but we still received data,
            # count it as an ingested (partial) chunk for API compatibility
            # with the task 3.1 behaviour where every call increments the count.
            if not complete_chunks:
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
