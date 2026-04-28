"""Tests for the CrisisLink TTS Service.

Covers:
- POST /api/v1/tts/synthesize — happy path returns audio/mpeg
- Language fallback for unsupported languages
- Error handling when TTS backend is unavailable (503)
- Timeout handling (> 3 s) skips segment
- Bearer token authentication (401 on missing/invalid token)

Requirements: 5.3, 5.5
"""

import pytest
from httpx import ASGITransport, AsyncClient

from tts.app import app, set_tts_client
from tts.tts_client import MockTTSClient

BASE_URL = "http://testserver"
VALID_TOKEN = "crisislink-dev-token"
AUTH_HEADER = {"Authorization": f"Bearer {VALID_TOKEN}"}


def _make_body(
    text: str = "Stay calm, help is on the way.",
    language: str = "hi",
    voice_name: str = "",
    speaking_rate: float = 1.0,
) -> dict:
    return {
        "text": text,
        "language": language,
        "voice_config": {
            "name": voice_name,
            "speaking_rate": speaking_rate,
        },
    }


@pytest.fixture(autouse=True)
def _reset_client():
    """Install a fresh MockTTSClient before each test."""
    set_tts_client(MockTTSClient())
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


# -----------------------------------------------------------------------
# Authentication tests
# -----------------------------------------------------------------------


class TestAuthentication:
    """Bearer token authentication middleware tests."""

    async def test_rejects_missing_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
        )
        assert resp.status_code in (401, 403)

    async def test_rejects_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    async def test_accepts_valid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Happy-path synthesis tests
# -----------------------------------------------------------------------


class TestSynthesisEndpoint:
    """POST /api/v1/tts/synthesize — successful synthesis."""

    async def test_returns_audio_mpeg_content_type(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(language="hi"),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"

    async def test_returns_binary_audio_body(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(text="Hello"),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        # MockTTSClient returns fake MP3 header + text bytes
        assert len(resp.content) > 0
        assert resp.content[:4] == b"\xff\xfb\x90\x00"

    async def test_supported_languages_return_audio(self, client: AsyncClient):
        """All five Indian languages + English should produce audio."""
        for lang in ("hi", "ta", "te", "bn", "mr", "en"):
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json=_make_body(language=lang),
                headers=AUTH_HEADER,
            )
            assert resp.status_code == 200, f"Failed for language {lang}"
            assert resp.headers["content-type"] == "audio/mpeg"

    async def test_voice_config_passed_to_client(self, client: AsyncClient):
        mock = MockTTSClient()
        set_tts_client(mock)
        await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(
                voice_name="hi-IN-Neural2-B",
                speaking_rate=1.5,
            ),
            headers=AUTH_HEADER,
        )
        assert mock.last_request is not None
        assert mock.last_request["voice_name"] == "hi-IN-Neural2-B"
        assert mock.last_request["speaking_rate"] == 1.5


# -----------------------------------------------------------------------
# Language fallback tests (Task 7.2)
# -----------------------------------------------------------------------


class TestLanguageFallback:
    """Unsupported language falls back to Hindi or English TTS."""

    async def test_unsupported_language_returns_200_with_fallback(
        self, client: AsyncClient
    ):
        """Kannada (kn) is not in the supported list — should fall back."""
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(language="kn"),
            headers=AUTH_HEADER,
        )
        # Fallback produces audio in a different language → JSON response
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert data["language"] == "kn"
        assert data["fallback_language"] in ("hi", "en")
        assert data["audio_base64"] is not None

    async def test_fallback_includes_original_text(self, client: AsyncClient):
        original = "ಸಹಾಯ ಬರುತ್ತಿದೆ"
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(text=original, language="kn"),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["text"] == original

    async def test_fallback_prefers_hindi_over_english(self, client: AsyncClient):
        """Hindi is first in the fallback chain."""
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(language="gu"),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["fallback_language"] == "hi"


# -----------------------------------------------------------------------
# TTS unavailability tests (Task 7.2 — 503 scenario)
# -----------------------------------------------------------------------


class TestTTSUnavailable:
    """Google Cloud TTS unavailable → return text guidance for manual relay."""

    async def test_unavailable_returns_503_with_text(self, client: AsyncClient):
        set_tts_client(MockTTSClient(should_fail=True))
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "fallback"
        assert "unavailable" in data["reason"].lower()
        assert data["text"] == "Stay calm, help is on the way."

    async def test_unavailable_includes_language(self, client: AsyncClient):
        set_tts_client(MockTTSClient(should_fail=True))
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(language="ta"),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["language"] == "ta"

    async def test_unavailable_no_audio(self, client: AsyncClient):
        set_tts_client(MockTTSClient(should_fail=True))
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["audio_base64"] is None


# -----------------------------------------------------------------------
# Timeout handling tests (Task 7.2 — > 3 s)
# -----------------------------------------------------------------------


class TestSynthesisTimeout:
    """Audio synthesis timeout (> 3 s) → skip segment, return text fallback."""

    async def test_timeout_returns_503_with_reason(self, client: AsyncClient):
        set_tts_client(MockTTSClient(should_timeout=True))
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "fallback"
        assert "timed out" in data["reason"].lower()

    async def test_timeout_includes_original_text(self, client: AsyncClient):
        set_tts_client(MockTTSClient(should_timeout=True))
        guidance = "Apply pressure to the wound."
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(text=guidance),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["text"] == guidance

    async def test_timeout_no_audio(self, client: AsyncClient):
        set_tts_client(MockTTSClient(should_timeout=True))
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["audio_base64"] is None


# -----------------------------------------------------------------------
# Request validation tests
# -----------------------------------------------------------------------


class TestRequestValidation:
    """Input validation on the synthesize endpoint."""

    async def test_empty_text_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(text=""),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422

    async def test_missing_language_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json={"text": "hello", "voice_config": {"name": "", "speaking_rate": 1.0}},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422

    async def test_speaking_rate_out_of_range_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tts/synthesize",
            json=_make_body(speaking_rate=5.0),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422
