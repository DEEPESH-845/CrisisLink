"""TTS Service logic with error handling and language fallback.

Implements the core synthesis workflow:
1. Attempt synthesis in the requested language.
2. If the language is unsupported, fall back to Hindi then English.
3. If the TTS backend is unavailable (503), return text for manual relay.
4. If synthesis times out (> 3 s), skip the segment and return text fallback.

Requirements: 5.3, 5.5
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from .tts_client import (
    FALLBACK_LANGUAGES,
    SUPPORTED_LANGUAGES,
    TTSClient,
    TTSClientError,
    TTSTimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Outcome of a synthesis attempt."""

    audio: bytes | None = None
    used_language: str | None = None
    fallback_used: bool = False
    original_text: str = ""
    original_language: str = ""
    error_reason: str | None = None


def _resolve_voice(language: str, voice_name: str) -> tuple[str, str]:
    """Return (language_code, voice_name) for the given language.

    If *voice_name* is provided and non-empty it is used as-is.
    Otherwise the default Neural2 voice for *language* is selected.
    The language code is expanded to a BCP-47 locale (e.g. ``hi`` → ``hi-IN``).
    """
    if not voice_name:
        voice_name = SUPPORTED_LANGUAGES.get(language, "")
    # Google Cloud TTS expects a full locale like "hi-IN".
    locale = f"{language}-IN" if len(language) == 2 else language
    return locale, voice_name


def is_language_supported(language: str) -> bool:
    """Return True if *language* has a Neural2 voice mapping."""
    return language in SUPPORTED_LANGUAGES


async def synthesize_speech(
    client: TTSClient,
    text: str,
    language: str,
    voice_name: str = "",
    speaking_rate: float = 1.0,
) -> SynthesisResult:
    """High-level synthesis with fallback and error handling.

    Parameters
    ----------
    client:
        A ``TTSClient`` implementation (real or mock).
    text:
        The guidance text to synthesize.
    language:
        ISO 639-1 language code requested by the caller.
    voice_name:
        Optional explicit voice name override.
    speaking_rate:
        Speaking rate multiplier.

    Returns
    -------
    SynthesisResult
        Contains audio bytes on success, or an error reason with the
        original text for manual relay on failure.
    """
    result = SynthesisResult(original_text=text, original_language=language)

    # ------------------------------------------------------------------
    # 1. Determine the language to use (with fallback for unsupported)
    # ------------------------------------------------------------------
    languages_to_try: list[str] = []

    if is_language_supported(language):
        languages_to_try.append(language)
    else:
        # Unsupported language → try fallback chain
        logger.warning(
            "Language '%s' not supported for TTS; trying fallback chain %s",
            language,
            FALLBACK_LANGUAGES,
        )
        result.fallback_used = True

    # Always append fallback languages so we have a safety net
    for fb in FALLBACK_LANGUAGES:
        if fb not in languages_to_try:
            languages_to_try.append(fb)

    # ------------------------------------------------------------------
    # 2. Attempt synthesis in each candidate language
    # ------------------------------------------------------------------
    for lang in languages_to_try:
        locale, resolved_voice = _resolve_voice(lang, voice_name if lang == language else "")
        try:
            audio = await client.synthesize(
                text=text,
                language_code=locale,
                voice_name=resolved_voice,
                speaking_rate=speaking_rate,
            )
            result.audio = audio
            result.used_language = lang
            if lang != language:
                result.fallback_used = True
            return result

        except TTSTimeoutError:
            # Timeout (> 3 s) — skip this segment, return text fallback
            logger.warning(
                "TTS synthesis timed out for language '%s'; skipping segment.",
                lang,
            )
            result.error_reason = (
                f"Audio synthesis timed out (>{lang}). "
                "Segment skipped — please relay guidance manually."
            )
            return result

        except TTSClientError:
            # Backend unavailable — if this is the last language, give up
            logger.warning(
                "TTS backend unavailable for language '%s'.",
                lang,
            )
            continue  # try next fallback language

    # ------------------------------------------------------------------
    # 3. All attempts failed — return text for manual relay (503 scenario)
    # ------------------------------------------------------------------
    result.error_reason = (
        "Google Cloud TTS is currently unavailable. "
        "Please relay the following guidance to the caller manually."
    )
    return result


def build_fallback_response_dict(result: SynthesisResult) -> dict:
    """Build a JSON-serialisable dict for a fallback (non-audio) response."""
    resp: dict = {
        "status": "fallback",
        "reason": result.error_reason or "TTS unavailable",
        "text": result.original_text,
        "language": result.original_language,
    }
    if result.fallback_used and result.audio is not None:
        resp["fallback_language"] = result.used_language
        resp["audio_base64"] = base64.b64encode(result.audio).decode("ascii")
    else:
        resp["fallback_language"] = None
        resp["audio_base64"] = None
    return resp
