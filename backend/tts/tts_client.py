"""Protocol and implementations for Google Cloud TTS interaction.

Provides a ``TTSClient`` protocol so the service layer can be tested with
a mock client while production uses the real Google Cloud TTS API.

Requirements: 5.3
"""

from __future__ import annotations

import asyncio
from typing import Protocol


class TTSClientError(Exception):
    """Raised when the TTS backend is unavailable (maps to HTTP 503)."""


class TTSTimeoutError(Exception):
    """Raised when audio synthesis exceeds the allowed timeout."""


class TTSClient(Protocol):
    """Abstract interface for text-to-speech synthesis."""

    async def synthesize(
        self,
        text: str,
        language_code: str,
        voice_name: str,
        speaking_rate: float,
    ) -> bytes:
        """Synthesize *text* and return raw audio bytes (MP3).

        Raises
        ------
        TTSClientError
            If the TTS backend is unreachable or returns a server error.
        TTSTimeoutError
            If synthesis takes longer than the allowed timeout.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Supported Indian languages → default Neural2 voice mapping
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: dict[str, str] = {
    "hi": "hi-IN-Neural2-A",
    "ta": "ta-IN-Neural2-A",
    "te": "te-IN-Neural2-A",
    "bn": "bn-IN-Neural2-A",
    "mr": "mr-IN-Neural2-A",
    "en": "en-IN-Neural2-A",
}

# Ordered fallback chain when the requested language is not supported.
FALLBACK_LANGUAGES: list[str] = ["hi", "en"]

SYNTHESIS_TIMEOUT_SECONDS: float = 3.0


# ---------------------------------------------------------------------------
# Mock implementation for testing / development
# ---------------------------------------------------------------------------


class MockTTSClient:
    """In-memory mock that returns deterministic fake audio bytes.

    Useful for unit tests and local development without Google Cloud
    credentials.
    """

    def __init__(
        self,
        *,
        should_fail: bool = False,
        should_timeout: bool = False,
        latency: float = 0.0,
    ) -> None:
        self.should_fail = should_fail
        self.should_timeout = should_timeout
        self.latency = latency
        self.last_request: dict | None = None

    async def synthesize(
        self,
        text: str,
        language_code: str,
        voice_name: str,
        speaking_rate: float,
    ) -> bytes:
        self.last_request = {
            "text": text,
            "language_code": language_code,
            "voice_name": voice_name,
            "speaking_rate": speaking_rate,
        }

        if self.latency > 0:
            await asyncio.sleep(self.latency)

        if self.should_timeout:
            raise TTSTimeoutError("Synthesis exceeded timeout")

        if self.should_fail:
            raise TTSClientError("TTS backend unavailable")

        # Return a small fake MP3 header so callers can verify binary content.
        fake_mp3_header = b"\xff\xfb\x90\x00"
        return fake_mp3_header + text.encode("utf-8")


# ---------------------------------------------------------------------------
# Real Google Cloud TTS client (thin wrapper)
# ---------------------------------------------------------------------------


class GoogleCloudTTSClient:
    """Production client that calls the Google Cloud Text-to-Speech API.

    Requires ``GOOGLE_APPLICATION_CREDENTIALS`` or equivalent ADC setup.
    """

    def __init__(self, timeout: float = SYNTHESIS_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    async def synthesize(
        self,
        text: str,
        language_code: str,
        voice_name: str,
        speaking_rate: float,
    ) -> bytes:
        try:
            from google.cloud import texttospeech  # type: ignore[import-untyped]
        except ImportError as exc:
            raise TTSClientError(
                "google-cloud-texttospeech is not installed"
            ) from exc

        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.synthesize_speech,
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config,
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TTSTimeoutError(
                f"Synthesis timed out after {self._timeout}s"
            ) from exc
        except Exception as exc:
            raise TTSClientError(f"TTS backend error: {exc}") from exc

        return response.audio_content  # type: ignore[no-any-return]
