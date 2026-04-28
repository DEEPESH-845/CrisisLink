"""Tests for the CrisisLink Speech Ingestion Service.

Covers:
- POST /api/v1/calls/{call_id}/audio-stream  (202 Accepted)
- GET  /api/v1/calls/{call_id}/transcript     (200 OK / 404)
- Bearer token authentication (401 on missing/invalid token)

Requirements: 1.1, 1.2
"""

import pytest
from httpx import ASGITransport, AsyncClient

from speech_ingestion.app import app, store

BASE_URL = "http://testserver"
VALID_TOKEN = "crisislink-dev-token"
AUTH_HEADER = {"Authorization": f"Bearer {VALID_TOKEN}"}

# A small fake PCM audio chunk (16 bytes = 8 samples at 16-bit).
FAKE_AUDIO_CHUNK = b"\x00\x01" * 8


@pytest.fixture(autouse=True)
def _reset_store():
    """Clear the in-memory store before each test."""
    store.reset()
    yield
    store.reset()


@pytest.fixture
async def client():
    """Provide an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


# -----------------------------------------------------------------------
# Authentication tests
# -----------------------------------------------------------------------


class TestAuthentication:
    """Bearer token authentication middleware tests."""

    async def test_audio_stream_rejects_missing_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/audio-stream",
            content=FAKE_AUDIO_CHUNK,
        )
        assert resp.status_code == 403  # HTTPBearer returns 403 when header absent

    async def test_audio_stream_rejects_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    async def test_transcript_rejects_missing_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/calls/CALL-001/transcript")
        assert resp.status_code == 403

    async def test_transcript_rejects_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/calls/CALL-001/transcript",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401


# -----------------------------------------------------------------------
# Audio stream endpoint tests
# -----------------------------------------------------------------------


class TestAudioStreamEndpoint:
    """POST /api/v1/calls/{call_id}/audio-stream tests."""

    async def test_returns_202_accepted(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 202

    async def test_response_body_schema(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["call_id"] == "CALL-001"
        assert data["status"] == "accepted"
        assert data["chunks_processed"] == 1

    async def test_chunks_processed_increments(self, client: AsyncClient):
        for i in range(1, 4):
            resp = await client.post(
                "/api/v1/calls/CALL-002/audio-stream",
                content=FAKE_AUDIO_CHUNK,
                headers=AUTH_HEADER,
            )
            assert resp.json()["chunks_processed"] == i

    async def test_empty_body_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/audio-stream",
            content=b"",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    async def test_different_calls_tracked_independently(self, client: AsyncClient):
        await client.post(
            "/api/v1/calls/CALL-A/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        await client.post(
            "/api/v1/calls/CALL-A/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        resp_b = await client.post(
            "/api/v1/calls/CALL-B/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        assert resp_b.json()["chunks_processed"] == 1


# -----------------------------------------------------------------------
# Transcript endpoint tests
# -----------------------------------------------------------------------


class TestTranscriptEndpoint:
    """GET /api/v1/calls/{call_id}/transcript tests."""

    async def test_returns_404_for_unknown_call(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/calls/NONEXISTENT/transcript",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404

    async def test_returns_transcript_after_ingestion(self, client: AsyncClient):
        # Ingest a chunk first
        await client.post(
            "/api/v1/calls/CALL-001/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        resp = await client.get(
            "/api/v1/calls/CALL-001/transcript",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["call_id"] == "CALL-001"
        assert "transcript" in data
        assert "language_detected" in data
        assert data["chunks_processed"] == 1

    async def test_transcript_response_schema(self, client: AsyncClient):
        """Verify all required fields are present in the response."""
        await client.post(
            "/api/v1/calls/CALL-003/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        resp = await client.get(
            "/api/v1/calls/CALL-003/transcript",
            headers=AUTH_HEADER,
        )
        data = resp.json()
        required_fields = {"call_id", "transcript", "language_detected", "chunks_processed"}
        assert required_fields.issubset(data.keys())

    async def test_transcript_chunks_count_matches_ingested(self, client: AsyncClient):
        for _ in range(5):
            await client.post(
                "/api/v1/calls/CALL-004/audio-stream",
                content=FAKE_AUDIO_CHUNK,
                headers=AUTH_HEADER,
            )
        resp = await client.get(
            "/api/v1/calls/CALL-004/transcript",
            headers=AUTH_HEADER,
        )
        assert resp.json()["chunks_processed"] == 5

    async def test_default_language_is_unknown(self, client: AsyncClient):
        """Before real transcription, language_detected defaults to 'unknown'."""
        await client.post(
            "/api/v1/calls/CALL-005/audio-stream",
            content=FAKE_AUDIO_CHUNK,
            headers=AUTH_HEADER,
        )
        resp = await client.get(
            "/api/v1/calls/CALL-005/transcript",
            headers=AUTH_HEADER,
        )
        assert resp.json()["language_detected"] == "unknown"
