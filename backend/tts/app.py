"""FastAPI application for the CrisisLink TTS Service.

Endpoints
---------
POST /api/v1/tts/synthesize
    Accept text, language, and voice configuration.  Returns binary audio
    (MP3) on success, or a JSON fallback response when TTS is unavailable,
    the language is unsupported, or synthesis times out.

The endpoint requires a valid Bearer token in the Authorization header.

Requirements: 5.3, 5.5
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Response, status
from fastapi.responses import JSONResponse

from .auth import verify_bearer_token
from .schemas import SynthesizeRequest
from .service import build_fallback_response_dict, synthesize_speech
from .tts_client import MockTTSClient, TTSClient

app = FastAPI(
    title="CrisisLink TTS Service",
    version="0.1.0",
    description=(
        "Converts guidance text into natural speech using Google Cloud TTS "
        "Neural2 voices for Indian languages."
    ),
)

# ---------------------------------------------------------------------------
# TTS client dependency — swappable for testing
# ---------------------------------------------------------------------------

_tts_client: TTSClient = MockTTSClient()


def get_tts_client() -> TTSClient:
    """Return the active TTS client instance."""
    return _tts_client


def set_tts_client(client: TTSClient) -> None:
    """Replace the active TTS client (used in tests)."""
    global _tts_client
    _tts_client = client


# ---------------------------------------------------------------------------
# Synthesis endpoint
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/tts/synthesize",
    summary="Synthesize guidance text into speech",
    responses={
        200: {
            "description": "Binary audio (MP3)",
            "content": {"audio/mpeg": {}},
        },
        503: {
            "description": "TTS unavailable — text fallback returned",
            "content": {"application/json": {}},
        },
    },
)
async def synthesize(
    body: SynthesizeRequest,
    _token: str = Depends(verify_bearer_token),
    client: TTSClient = Depends(get_tts_client),
) -> Response:
    """Synthesize *body.text* into speech audio.

    On success returns ``audio/mpeg`` binary.  When the TTS backend is
    unavailable, the language is unsupported (with no fallback audio), or
    synthesis times out, a JSON body is returned with the original text
    for manual relay by the operator.
    """
    result = await synthesize_speech(
        client=client,
        text=body.text,
        language=body.language,
        voice_name=body.voice_config.name,
        speaking_rate=body.voice_config.speaking_rate,
    )

    # --- Happy path: audio produced (possibly in a fallback language) ---
    if result.audio is not None and result.error_reason is None:
        if result.fallback_used:
            # Audio was produced in a fallback language.  Return JSON with
            # the original text *and* the fallback audio so the operator
            # can decide how to relay.
            payload = build_fallback_response_dict(result)
            return JSONResponse(
                content=payload,
                status_code=status.HTTP_200_OK,
            )
        # Direct success — return binary audio
        return Response(
            content=result.audio,
            media_type="audio/mpeg",
            status_code=status.HTTP_200_OK,
        )

    # --- Error path: no audio produced ---
    payload = build_fallback_response_dict(result)
    return JSONResponse(
        content=payload,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
