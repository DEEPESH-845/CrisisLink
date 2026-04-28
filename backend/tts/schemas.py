"""Request/response schemas for the TTS Service.

Requirements: 5.3
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceConfig(BaseModel):
    """Voice configuration for TTS synthesis."""

    name: str = Field(
        default="",
        description="Google Cloud TTS voice name (e.g. 'hi-IN-Neural2-A'). "
        "If empty, a default voice for the requested language is used.",
    )
    speaking_rate: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Speaking rate multiplier (0.25–4.0). Default is 1.0.",
    )


class SynthesizeRequest(BaseModel):
    """Request body for POST /api/v1/tts/synthesize."""

    text: str = Field(
        ...,
        min_length=1,
        description="Text to synthesize into speech.",
    )
    language: str = Field(
        ...,
        min_length=2,
        description="ISO 639-1 language code (e.g. 'hi', 'ta', 'te', 'bn', 'mr', 'en').",
    )
    voice_config: VoiceConfig = Field(
        default_factory=VoiceConfig,
        description="Optional voice configuration overrides.",
    )


class TTSFallbackResponse(BaseModel):
    """Returned when TTS audio cannot be produced and text guidance is
    provided instead for manual relay by the operator.
    """

    status: str = Field(
        default="fallback",
        description="Indicates the response is a text fallback, not audio.",
    )
    reason: str = Field(
        ...,
        description="Human-readable reason why audio could not be produced.",
    )
    text: str = Field(
        ...,
        description="Original guidance text for the operator to relay manually.",
    )
    language: str = Field(
        ...,
        description="Language code of the original text.",
    )
    fallback_language: str | None = Field(
        default=None,
        description="Language code used for fallback TTS, if any.",
    )
    audio_base64: str | None = Field(
        default=None,
        description="Base64-encoded fallback audio, if a fallback language was used.",
    )
