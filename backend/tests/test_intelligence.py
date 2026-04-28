"""Tests for the CrisisLink Intelligence Service.

Covers:
- POST /api/v1/calls/{call_id}/classify  (200 OK)
- POST /api/v1/calls/{call_id}/guidance  (200 OK)
- Bearer token authentication (401 on missing/invalid token)
- Firebase RTDB transcript listener infrastructure
- Guidance generation only for CRITICAL/HIGH severity

Requirements: 2.1, 2.7, 5.1
"""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from intelligence.app import app, reset_listeners, get_transcript_snapshot
from shared.models import (
    CallerRole,
    CallerState,
    EmergencyClassification,
    EmergencyType,
    PanicLevel,
    Severity,
)

BASE_URL = "http://testserver"
VALID_TOKEN = "crisislink-dev-token"
AUTH_HEADER = {"Authorization": f"Bearer {VALID_TOKEN}"}


def _make_classification(
    call_id: str = "CALL-001",
    severity: Severity = Severity.CRITICAL,
    emergency_type: EmergencyType = EmergencyType.MEDICAL,
) -> dict:
    """Build a valid Emergency_Classification dict for request bodies."""
    return EmergencyClassification(
        call_id=call_id,
        emergency_type=emergency_type,
        severity=severity,
        caller_state=CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.VICTIM,
        ),
        language_detected="hi",
        key_facts=["chest pain", "elderly person"],
        confidence=0.85,
        timestamp=datetime.now(timezone.utc),
        model_version="stub-v0",
    ).model_dump(mode="json")


@pytest.fixture(autouse=True)
def _reset():
    """Clear listener state before each test."""
    reset_listeners()
    yield
    reset_listeners()


@pytest.fixture
async def client():
    """Provide an httpx AsyncClient wired to the Intelligence FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


# -----------------------------------------------------------------------
# Authentication tests
# -----------------------------------------------------------------------


class TestAuthentication:
    """Bearer token authentication middleware tests."""

    async def test_classify_rejects_missing_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/classify",
            json={"transcript": "help"},
        )
        assert resp.status_code in (401, 403)

    async def test_classify_rejects_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/classify",
            json={"transcript": "help"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    async def test_guidance_rejects_missing_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/guidance",
            json={
                "classification": _make_classification(),
                "caller_state": {"panic_level": "CALM", "caller_role": "BYSTANDER"},
            },
        )
        assert resp.status_code in (401, 403)

    async def test_guidance_rejects_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/guidance",
            json={
                "classification": _make_classification(),
                "caller_state": {"panic_level": "CALM", "caller_role": "BYSTANDER"},
            },
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401


# -----------------------------------------------------------------------
# Classify endpoint tests
# -----------------------------------------------------------------------


class TestClassifyEndpoint:
    """POST /api/v1/calls/{call_id}/classify tests."""

    async def test_returns_200_with_valid_request(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/classify",
            json={"transcript": "There is a fire in the building"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    async def test_response_contains_classification(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/classify",
            json={"transcript": "Someone collapsed on the road"},
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert "classification" in data
        classification = data["classification"]
        assert classification["call_id"] == "CALL-001"

    async def test_classification_has_required_fields(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-010/classify",
            json={"transcript": "accident on highway"},
            headers=AUTH_HEADER,
        )
        classification = resp.json()["classification"]
        required_fields = {
            "call_id",
            "emergency_type",
            "severity",
            "caller_state",
            "language_detected",
            "key_facts",
            "confidence",
            "timestamp",
            "model_version",
        }
        assert required_fields.issubset(classification.keys())

    async def test_classification_enum_values_are_valid(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-011/classify",
            json={"transcript": "help me"},
            headers=AUTH_HEADER,
        )
        c = resp.json()["classification"]
        assert c["emergency_type"] in [e.value for e in EmergencyType]
        assert c["severity"] in [s.value for s in Severity]
        assert c["caller_state"]["panic_level"] in [p.value for p in PanicLevel]
        assert c["caller_state"]["caller_role"] in [r.value for r in CallerRole]

    async def test_confidence_in_valid_range(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-012/classify",
            json={"transcript": "fire fire"},
            headers=AUTH_HEADER,
        )
        confidence = resp.json()["classification"]["confidence"]
        assert 0.0 <= confidence <= 1.0

    async def test_classify_registers_transcript_listener(self, client: AsyncClient):
        """Calling classify should start a transcript listener for the call."""
        assert get_transcript_snapshot("CALL-LISTEN") is None
        await client.post(
            "/api/v1/calls/CALL-LISTEN/classify",
            json={"transcript": "test"},
            headers=AUTH_HEADER,
        )
        # After classify, the listener should be registered
        assert get_transcript_snapshot("CALL-LISTEN") is not None

    async def test_classify_rejects_missing_transcript(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/classify",
            json={},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422

    async def test_different_calls_produce_correct_call_id(self, client: AsyncClient):
        for cid in ("CALL-A", "CALL-B", "CALL-C"):
            resp = await client.post(
                f"/api/v1/calls/{cid}/classify",
                json={"transcript": "emergency"},
                headers=AUTH_HEADER,
            )
            assert resp.json()["classification"]["call_id"] == cid


# -----------------------------------------------------------------------
# Guidance endpoint tests
# -----------------------------------------------------------------------


class TestGuidanceEndpoint:
    """POST /api/v1/calls/{call_id}/guidance tests."""

    async def test_returns_200_with_valid_request(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/guidance",
            json={
                "classification": _make_classification(severity=Severity.CRITICAL),
                "caller_state": {
                    "panic_level": "PANIC_HIGH",
                    "caller_role": "VICTIM",
                },
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    async def test_response_contains_guidance_fields(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-002/guidance",
            json={
                "classification": _make_classification(
                    call_id="CALL-002", severity=Severity.HIGH
                ),
                "caller_state": {
                    "panic_level": "CALM",
                    "caller_role": "BYSTANDER",
                },
            },
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["call_id"] == "CALL-002"
        assert "guidance" in data

    async def test_guidance_generated_for_critical_severity(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-003/guidance",
            json={
                "classification": _make_classification(severity=Severity.CRITICAL),
                "caller_state": {
                    "panic_level": "PANIC_HIGH",
                    "caller_role": "VICTIM",
                },
            },
            headers=AUTH_HEADER,
        )
        assert resp.json()["guidance"] != ""

    async def test_guidance_generated_for_high_severity(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-004/guidance",
            json={
                "classification": _make_classification(severity=Severity.HIGH),
                "caller_state": {
                    "panic_level": "CALM",
                    "caller_role": "BYSTANDER",
                },
            },
            headers=AUTH_HEADER,
        )
        assert resp.json()["guidance"] != ""

    async def test_no_guidance_for_moderate_severity(self, client: AsyncClient):
        """Requirement 5.1: guidance only for CRITICAL or HIGH."""
        resp = await client.post(
            "/api/v1/calls/CALL-005/guidance",
            json={
                "classification": _make_classification(severity=Severity.MODERATE),
                "caller_state": {
                    "panic_level": "CALM",
                    "caller_role": "BYSTANDER",
                },
            },
            headers=AUTH_HEADER,
        )
        assert resp.json()["guidance"] == ""

    async def test_no_guidance_for_low_severity(self, client: AsyncClient):
        """Requirement 5.1: guidance only for CRITICAL or HIGH."""
        resp = await client.post(
            "/api/v1/calls/CALL-006/guidance",
            json={
                "classification": _make_classification(severity=Severity.LOW),
                "caller_state": {
                    "panic_level": "CALM",
                    "caller_role": "WITNESS",
                },
            },
            headers=AUTH_HEADER,
        )
        assert resp.json()["guidance"] == ""

    async def test_guidance_rejects_invalid_body(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/calls/CALL-001/guidance",
            json={"classification": "not-valid"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422


# -----------------------------------------------------------------------
# Transcript listener infrastructure tests
# -----------------------------------------------------------------------


class TestTranscriptListener:
    """Firebase RTDB transcript listener infrastructure tests."""

    async def test_listener_not_registered_initially(self, client: AsyncClient):
        assert get_transcript_snapshot("CALL-NEW") is None

    async def test_classify_starts_listener(self, client: AsyncClient):
        await client.post(
            "/api/v1/calls/CALL-NEW/classify",
            json={"transcript": "hello"},
            headers=AUTH_HEADER,
        )
        snapshot = get_transcript_snapshot("CALL-NEW")
        assert snapshot is not None

    async def test_multiple_calls_have_independent_listeners(self, client: AsyncClient):
        for cid in ("CALL-X", "CALL-Y"):
            await client.post(
                f"/api/v1/calls/{cid}/classify",
                json={"transcript": f"transcript for {cid}"},
                headers=AUTH_HEADER,
            )
        assert get_transcript_snapshot("CALL-X") is not None
        assert get_transcript_snapshot("CALL-Y") is not None

    async def test_reset_clears_all_listeners(self, client: AsyncClient):
        await client.post(
            "/api/v1/calls/CALL-Z/classify",
            json={"transcript": "test"},
            headers=AUTH_HEADER,
        )
        reset_listeners()
        assert get_transcript_snapshot("CALL-Z") is None
