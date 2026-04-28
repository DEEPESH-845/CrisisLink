"""Transcription protocol and implementations for the Speech Ingestion Service.

Defines a ``Transcriber`` protocol that any speech-to-text backend must
implement, plus a ``MockWhisperTranscriber`` for testing and a placeholder
``WhisperTranscriber`` for production use (requires GPU resources).

The 22 scheduled Indian languages supported for auto-detection are listed
in :data:`SCHEDULED_INDIAN_LANGUAGES`.

Requirements: 1.1, 1.2, 1.3
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# ISO 639-1 codes for the 22 scheduled Indian languages + English.
# Whisper Large-v3 supports all of these natively.
SCHEDULED_INDIAN_LANGUAGES: dict[str, str] = {
    "as": "Assamese",
    "bn": "Bengali",
    "bo": "Bodo",
    "doi": "Dogri",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "ks": "Kashmiri",
    "gom": "Konkani",
    "mai": "Maithili",
    "ml": "Malayalam",
    "mni": "Manipuri",
    "mr": "Marathi",
    "ne": "Nepali",
    "or": "Odia",
    "pa": "Punjabi",
    "sa": "Sanskrit",
    "sat": "Santali",
    "sd": "Sindhi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
    "en": "English",
}


@dataclass
class TranscriptionResult:
    """Result of a single transcription call."""

    text: str
    language: str  # ISO 639-1 code (e.g. "hi", "ta", "en")
    confidence: float = 1.0  # model confidence in [0, 1]


@runtime_checkable
class Transcriber(Protocol):
    """Protocol that any speech-to-text backend must satisfy."""

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe a single audio chunk and return the result.

        Parameters
        ----------
        audio_chunk : bytes
            Raw PCM 16-bit, 16 kHz mono audio data (typically 500ms / 16 000 bytes).

        Returns
        -------
        TranscriptionResult
            The transcript text, detected language code, and confidence.
        """
        ...


class MockWhisperTranscriber:
    """Mock transcriber for testing — returns deterministic results.

    Useful for unit and integration tests where loading the real
    Whisper Large-v3 model is not feasible.
    """

    def __init__(
        self,
        default_text: str = "[mock transcript]",
        default_language: str = "hi",
        default_confidence: float = 0.95,
    ) -> None:
        self._default_text = default_text
        self._default_language = default_language
        self._default_confidence = default_confidence
        self.call_count: int = 0

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        """Return a deterministic transcription result."""
        self.call_count += 1
        return TranscriptionResult(
            text=self._default_text,
            language=self._default_language,
            confidence=self._default_confidence,
        )


class WhisperTranscriber:
    """Whisper Large-v3 transcriber for production use.

    This is a placeholder that documents the expected integration points.
    Actual model loading requires a Cloud Run instance with an NVIDIA T4 GPU
    and the ``openai-whisper`` or ``faster-whisper`` package installed.

    The real implementation would:
    1. Load the ``large-v3`` model on startup.
    2. Accept PCM audio bytes, convert to float32 numpy array.
    3. Call ``model.transcribe()`` with ``language=None`` for auto-detection.
    4. Return the detected text, language ISO code, and average log-prob
       converted to a 0–1 confidence score.
    """

    def __init__(self, model_name: str = "large-v3") -> None:
        self._model_name = model_name
        # In production: self._model = whisper.load_model(model_name)

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe using Whisper Large-v3.

        Raises ``NotImplementedError`` until deployed on a GPU-enabled
        Cloud Run instance.
        """
        raise NotImplementedError(
            f"WhisperTranscriber({self._model_name!r}) requires a GPU runtime. "
            "Use MockWhisperTranscriber for testing."
        )
