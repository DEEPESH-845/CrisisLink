"""Tests for the CrisisLink Dispatch Service.

Covers:
- Haversine distance calculation
- Unit filtering by status and radius
- Stale location detection
- Radius expansion (15 km → 30 km)
- Composite score calculation and normalization
- Ranking and top-3 selection
- Dispatch_Card generation
- Dispatch confirmation flow (status update, FCM, audit log)
- Bearer token authentication
- API endpoints (recommend + confirm)

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 8.3, 10.4
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from dispatch.app import (
    app,
    set_audit_logger,
    set_fcm_client,
    set_maps_client,
    set_unit_store,
)
from dispatch.confirmation import MockAuditLogger, MockFCMClient, confirm_dispatch
from dispatch.geospatial import (
    DEFAULT_RADIUS_KM,
    EXPANDED_RADIUS_KM,
    STALE_THRESHOLD_SECONDS,
    filter_units,
    filter_units_with_expansion,
    haversine_km,
)
from dispatch.maps_client import MockMapsClient, fallback_eta_minutes
from dispatch.ranking import (
    MAX_RECOMMENDATIONS,
    ScoredUnit,
    _compute_capability_match,
    compute_composite_scores,
    normalize_etas,
    rank_and_build_card,
)
from dispatch.unit_store import MockUnitStore
from shared.models import (
    CallerRole,
    CallerState,
    EmergencyClassification,
    EmergencyType,
    Location,
    PanicLevel,
    ResponseUnit,
    Severity,
    UnitStatus,
    UnitType,
)

BASE_URL = "http://testserver"
VALID_TOKEN = "crisislink-dev-token"
AUTH_HEADER = {"Authorization": f"Bearer {VALID_TOKEN}"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Central Delhi coordinates
DELHI_LAT, DELHI_LNG = 28.6139, 77.2090


def _make_classification(
    call_id: str = "CALL-001",
    severity: Severity = Severity.CRITICAL,
    emergency_type: EmergencyType = EmergencyType.MEDICAL,
    key_facts: list[str] | None = None,
) -> EmergencyClassification:
    return EmergencyClassification(
        call_id=call_id,
        emergency_type=emergency_type,
        severity=severity,
        caller_state=CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.VICTIM,
        ),
        language_detected="hi",
        key_facts=key_facts or ["chest pain", "elderly person"],
        confidence=0.85,
        timestamp=datetime.now(timezone.utc),
        model_version="stub-v0",
    )


def _make_unit(
    unit_id: str = "AMB_001",
    lat: float = DELHI_LAT + 0.01,
    lng: float = DELHI_LNG + 0.01,
    status: UnitStatus = UnitStatus.AVAILABLE,
    unit_type: UnitType = UnitType.AMBULANCE,
    capabilities: list[str] | None = None,
    last_updated: int | None = None,
) -> ResponseUnit:
    return ResponseUnit(
        unit_id=unit_id,
        type=unit_type,
        status=status,
        location=Location(lat=lat, lng=lng),
        hospital_or_station="AIIMS Delhi",
        capabilities=capabilities or ["cardiac", "trauma"],
        last_updated=last_updated or int(time.time()),
    )


def _classification_dict(
    call_id: str = "CALL-001",
    severity: Severity = Severity.CRITICAL,
    emergency_type: EmergencyType = EmergencyType.MEDICAL,
) -> dict:
    return _make_classification(call_id, severity, emergency_type).model_dump(mode="json")


def _recommend_body(call_id: str = "CALL-001") -> dict:
    return {
        "classification": _classification_dict(call_id=call_id),
        "caller_location": {"lat": DELHI_LAT, "lng": DELHI_LNG},
    }


# ---------------------------------------------------------------------------
# Haversine distance tests
# ---------------------------------------------------------------------------


class TestHaversine:
    """Haversine distance calculation tests."""

    def test_same_point_returns_zero(self):
        assert haversine_km(28.0, 77.0, 28.0, 77.0) == 0.0

    def test_known_distance_delhi_to_agra(self):
        # Delhi to Agra is approximately 200 km
        dist = haversine_km(28.6139, 77.2090, 27.1767, 78.0081)
        assert 160 < dist < 200

    def test_short_distance_within_city(self):
        # Two points ~1.5 km apart in Delhi
        dist = haversine_km(28.6139, 77.2090, 28.6239, 77.2090)
        assert 0.5 < dist < 2.0

    def test_symmetry(self):
        d1 = haversine_km(28.0, 77.0, 29.0, 78.0)
        d2 = haversine_km(29.0, 78.0, 28.0, 77.0)
        assert abs(d1 - d2) < 1e-10

    def test_distance_is_non_negative(self):
        assert haversine_km(0.0, 0.0, 90.0, 180.0) >= 0.0


# ---------------------------------------------------------------------------
# Unit filtering tests
# ---------------------------------------------------------------------------


class TestUnitFiltering:
    """Geospatial and status unit filtering tests."""

    def test_filters_by_available_status(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        units = [
            _make_unit("AMB_001", status=UnitStatus.AVAILABLE),
            _make_unit("AMB_002", status=UnitStatus.DISPATCHED),
            _make_unit("AMB_003", status=UnitStatus.ON_SCENE),
            _make_unit("AMB_004", status=UnitStatus.RETURNING),
        ]
        result = filter_units(units, caller, now_unix=time.time())
        assert len(result) == 1
        assert result[0].unit.unit_id == "AMB_001"

    def test_filters_by_radius(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        # One unit ~1 km away, one ~50 km away
        units = [
            _make_unit("NEAR", lat=DELHI_LAT + 0.01, lng=DELHI_LNG),
            _make_unit("FAR", lat=DELHI_LAT + 0.5, lng=DELHI_LNG),
        ]
        result = filter_units(units, caller, radius_km=15.0, now_unix=time.time())
        assert len(result) == 1
        assert result[0].unit.unit_id == "NEAR"

    def test_empty_units_returns_empty(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        result = filter_units([], caller, now_unix=time.time())
        assert result == []

    def test_all_unavailable_returns_empty(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        units = [
            _make_unit("AMB_001", status=UnitStatus.DISPATCHED),
            _make_unit("AMB_002", status=UnitStatus.ON_SCENE),
        ]
        result = filter_units(units, caller, now_unix=time.time())
        assert result == []

    def test_stale_location_flagged(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        now = time.time()
        units = [
            _make_unit("FRESH", last_updated=int(now - 30)),
            _make_unit("STALE_001", last_updated=int(now - 120)),
        ]
        result = filter_units(units, caller, now_unix=now)
        fresh = [r for r in result if r.unit.unit_id == "FRESH"]
        stale = [r for r in result if r.unit.unit_id == "STALE_001"]

        assert len(fresh) == 1
        assert fresh[0].location_stale is False
        assert len(stale) == 1
        assert stale[0].location_stale is True

    def test_stale_threshold_boundary(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        now = 1000000.0
        # Exactly at threshold — should NOT be stale (> 60, not >=)
        units = [_make_unit("BOUNDARY", last_updated=int(now - STALE_THRESHOLD_SECONDS))]
        result = filter_units(units, caller, now_unix=now)
        assert len(result) == 1
        assert result[0].location_stale is False

    def test_expansion_to_30km(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        # Unit ~20 km away — outside 15 km but inside 30 km
        units = [_make_unit("MID", lat=DELHI_LAT + 0.18, lng=DELHI_LNG)]
        result = filter_units_with_expansion(units, caller, now_unix=time.time())
        assert len(result) == 1
        assert result[0].unit.unit_id == "MID"

    def test_no_expansion_when_units_within_15km(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        units = [
            _make_unit("NEAR", lat=DELHI_LAT + 0.01, lng=DELHI_LNG),
            _make_unit("MID_001", lat=DELHI_LAT + 0.18, lng=DELHI_LNG),
        ]
        result = filter_units_with_expansion(units, caller, now_unix=time.time())
        # Only the near unit should be returned (15 km filter, no expansion)
        unit_ids = {r.unit.unit_id for r in result}
        assert "NEAR" in unit_ids
        assert "MID_001" not in unit_ids

    def test_no_units_at_all_returns_empty(self):
        caller = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        result = filter_units_with_expansion([], caller, now_unix=time.time())
        assert result == []


# ---------------------------------------------------------------------------
# ETA and Maps client tests
# ---------------------------------------------------------------------------


class TestMapsClient:
    """Maps client and fallback ETA tests."""

    async def test_mock_maps_client_returns_eta(self):
        client = MockMapsClient(speed_kmh=60.0)
        origin = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        dest = Location(lat=DELHI_LAT + 0.01, lng=DELHI_LNG)
        eta = await client.get_eta_minutes(origin, dest)
        assert eta is not None
        assert eta > 0

    async def test_mock_maps_client_same_point_zero_eta(self):
        client = MockMapsClient()
        loc = Location(lat=DELHI_LAT, lng=DELHI_LNG)
        eta = await client.get_eta_minutes(loc, loc)
        assert eta == 0.0

    def test_fallback_eta_calculation(self):
        # 10 km at 40 km/h = 15 minutes
        assert fallback_eta_minutes(10.0) == pytest.approx(15.0)

    def test_fallback_eta_zero_distance(self):
        assert fallback_eta_minutes(0.0) == 0.0


# ---------------------------------------------------------------------------
# Composite score and ranking tests
# ---------------------------------------------------------------------------


class TestRanking:
    """Composite score calculation and ranking tests."""

    def test_normalize_etas_basic(self):
        result = normalize_etas([5.0, 10.0, 15.0])
        assert result == pytest.approx([0.0, 0.5, 1.0])

    def test_normalize_etas_all_equal(self):
        result = normalize_etas([7.0, 7.0, 7.0])
        assert result == [0.0, 0.0, 0.0]

    def test_normalize_etas_empty(self):
        assert normalize_etas([]) == []

    def test_normalize_etas_single(self):
        result = normalize_etas([5.0])
        assert result == [0.0]

    def test_composite_score_formula(self):
        """Verify composite = 0.6 * ETA_norm + 0.4 * (1 - capability_match)."""
        units = [
            ScoredUnit("U1", "ambulance", "H1", eta_minutes=5.0, capability_match=1.0, distance_km=3.0),
            ScoredUnit("U2", "ambulance", "H2", eta_minutes=15.0, capability_match=0.0, distance_km=10.0),
        ]
        scored = compute_composite_scores(units)
        # U1: ETA_norm=0.0, cap=1.0 → 0.6*0 + 0.4*(1-1) = 0.0
        # U2: ETA_norm=1.0, cap=0.0 → 0.6*1 + 0.4*(1-0) = 1.0
        assert scored[0][0].unit_id == "U1"
        assert scored[0][1] == pytest.approx(0.0)
        assert scored[1][0].unit_id == "U2"
        assert scored[1][1] == pytest.approx(1.0)

    def test_ranking_ascending_order(self):
        units = [
            ScoredUnit("U_BAD", "ambulance", "H1", eta_minutes=20.0, capability_match=0.0, distance_km=15.0),
            ScoredUnit("U_MID", "ambulance", "H2", eta_minutes=10.0, capability_match=0.5, distance_km=7.0),
            ScoredUnit("U_BEST", "ambulance", "H3", eta_minutes=5.0, capability_match=1.0, distance_km=3.0),
        ]
        scored = compute_composite_scores(units)
        ids = [s[0].unit_id for s in scored]
        assert ids[0] == "U_BEST"
        # Scores should be ascending
        scores = [s[1] for s in scored]
        assert scores == sorted(scores)

    def test_top_3_selection(self):
        classification = _make_classification()
        units = [
            ScoredUnit(f"U{i}", "ambulance", f"H{i}", eta_minutes=float(i), capability_match=0.5, distance_km=float(i))
            for i in range(1, 6)
        ]
        card = rank_and_build_card("CALL-001", units, classification)
        assert len(card.recommendations) == MAX_RECOMMENDATIONS

    def test_fewer_than_3_units(self):
        classification = _make_classification()
        units = [
            ScoredUnit("U1", "ambulance", "H1", eta_minutes=5.0, capability_match=0.8, distance_km=3.0),
            ScoredUnit("U2", "ambulance", "H2", eta_minutes=10.0, capability_match=0.6, distance_km=7.0),
        ]
        card = rank_and_build_card("CALL-002", units, classification)
        assert len(card.recommendations) == 2

    def test_single_unit(self):
        classification = _make_classification()
        units = [
            ScoredUnit("U1", "ambulance", "H1", eta_minutes=5.0, capability_match=0.8, distance_km=3.0),
        ]
        card = rank_and_build_card("CALL-003", units, classification)
        assert len(card.recommendations) == 1

    def test_empty_units_produces_empty_card(self):
        classification = _make_classification()
        card = rank_and_build_card("CALL-004", [], classification)
        assert len(card.recommendations) == 0

    def test_dispatch_card_fields(self):
        classification = _make_classification(call_id="CALL-005")
        units = [
            ScoredUnit("U1", "ambulance", "AIIMS", eta_minutes=5.0, capability_match=0.9, distance_km=3.0),
        ]
        card = rank_and_build_card("CALL-005", units, classification)
        assert card.call_id == "CALL-005"
        assert card.generated_at is not None
        assert card.classification_ref is not None
        rec = card.recommendations[0]
        assert rec.unit_id == "U1"
        assert rec.unit_type == "ambulance"
        assert rec.hospital_or_station == "AIIMS"
        assert rec.eta_minutes > 0
        assert 0.0 <= rec.capability_match <= 1.0
        assert rec.distance_km > 0

    def test_zero_eta_and_zero_capability(self):
        """Edge case: all ETAs zero, all capabilities zero."""
        units = [
            ScoredUnit("U1", "ambulance", "H1", eta_minutes=0.0, capability_match=0.0, distance_km=0.0),
            ScoredUnit("U2", "ambulance", "H2", eta_minutes=0.0, capability_match=0.0, distance_km=0.0),
        ]
        scored = compute_composite_scores(units)
        # Both should have same score: 0.6*0 + 0.4*(1-0) = 0.4
        assert scored[0][1] == pytest.approx(0.4)
        assert scored[1][1] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Capability match tests
# ---------------------------------------------------------------------------


class TestCapabilityMatch:
    """Capability match score computation tests."""

    def test_perfect_match(self):
        classification = _make_classification(
            emergency_type=EmergencyType.MEDICAL,
            key_facts=["cardiac arrest"],
        )
        score = _compute_capability_match(
            ["cardiac", "trauma", "als", "bls", "pediatric"], classification
        )
        assert score > 0.5

    def test_no_capabilities(self):
        classification = _make_classification()
        score = _compute_capability_match([], classification)
        assert score == 0.0

    def test_fire_capabilities(self):
        classification = _make_classification(emergency_type=EmergencyType.FIRE)
        score = _compute_capability_match(["fire", "hazmat", "rescue", "ladder"], classification)
        assert score > 0.5

    def test_unknown_type_neutral_score(self):
        classification = _make_classification(emergency_type=EmergencyType.UNKNOWN)
        score = _compute_capability_match(["cardiac"], classification)
        # UNKNOWN maps to no desired capabilities → neutral 0.5
        assert score == 0.5


# ---------------------------------------------------------------------------
# Dispatch confirmation tests
# ---------------------------------------------------------------------------


class TestConfirmation:
    """Dispatch confirmation flow tests."""

    async def test_updates_unit_status(self):
        store = MockUnitStore([_make_unit("AMB_010")])
        fcm = MockFCMClient()
        audit = MockAuditLogger()

        result = await confirm_dispatch("CALL-100", "AMB_010", store, fcm, audit)

        assert result["status"] == "dispatched"
        assert result["unit_id"] == "AMB_010"
        unit = store.get_unit("AMB_010")
        assert unit is not None
        assert unit.status == "dispatched"

    async def test_sends_fcm_notification(self):
        store = MockUnitStore([_make_unit("AMB_011")])
        fcm = MockFCMClient()
        audit = MockAuditLogger()

        await confirm_dispatch("CALL-101", "AMB_011", store, fcm, audit)

        assert len(fcm.sent_notifications) == 1
        notif = fcm.sent_notifications[0]
        assert notif["unit_id"] == "AMB_011"
        assert notif["call_id"] == "CALL-101"
        assert "payload" in notif

    async def test_writes_audit_log(self):
        store = MockUnitStore([_make_unit("AMB_012")])
        fcm = MockFCMClient()
        audit = MockAuditLogger()

        await confirm_dispatch("CALL-102", "AMB_012", store, fcm, audit)

        assert len(audit.entries) == 1
        entry = audit.entries[0]
        assert entry.call_id == "CALL-102"
        assert entry.event_type.value == "dispatch"
        assert entry.payload["unit_id"] == "AMB_012"
        assert entry.actor == "dispatch-service"

    async def test_audit_entry_has_required_fields(self):
        store = MockUnitStore([_make_unit("AMB_013")])
        fcm = MockFCMClient()
        audit = MockAuditLogger()

        await confirm_dispatch("CALL-103", "AMB_013", store, fcm, audit)

        entry = audit.entries[0]
        assert entry.log_id  # non-empty UUID
        assert entry.timestamp is not None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def _setup_dispatch_deps():
    """Set up mock dependencies for the dispatch app."""
    store = MockUnitStore()
    # Add some available units near Delhi
    store.add_unit(_make_unit("AMB_100", lat=DELHI_LAT + 0.01, lng=DELHI_LNG + 0.01))
    store.add_unit(_make_unit("AMB_101", lat=DELHI_LAT + 0.02, lng=DELHI_LNG + 0.02))
    store.add_unit(_make_unit("AMB_102", lat=DELHI_LAT + 0.03, lng=DELHI_LNG + 0.03))
    # One dispatched unit (should be filtered out)
    store.add_unit(_make_unit("AMB_103", status=UnitStatus.DISPATCHED))

    maps = MockMapsClient(speed_kmh=40.0)
    fcm = MockFCMClient()
    audit = MockAuditLogger()

    set_unit_store(store)
    set_maps_client(maps)
    set_fcm_client(fcm)
    set_audit_logger(audit)

    yield {"store": store, "maps": maps, "fcm": fcm, "audit": audit}


@pytest.fixture
async def client():
    """Provide an httpx AsyncClient wired to the Dispatch FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


class TestAuthentication:
    """Bearer token authentication middleware tests."""

    async def test_recommend_rejects_missing_token(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
        )
        assert resp.status_code in (401, 403)

    async def test_recommend_rejects_invalid_token(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    async def test_confirm_rejects_missing_token(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_100"},
        )
        assert resp.status_code in (401, 403)

    async def test_confirm_rejects_invalid_token(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_100"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401


class TestRecommendEndpoint:
    """POST /api/v1/calls/{call_id}/dispatch/recommend tests."""

    async def test_returns_200(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    async def test_response_contains_recommendations(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert "recommendations" in data
        assert "dispatch_card" in data
        assert len(data["recommendations"]) <= MAX_RECOMMENDATIONS
        assert len(data["recommendations"]) > 0

    async def test_recommendations_have_required_fields(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
            headers=AUTH_HEADER,
        )
        rec = resp.json()["recommendations"][0]
        required = {"unit_id", "unit_type", "hospital_or_station", "eta_minutes", "capability_match", "composite_score", "distance_km"}
        assert required.issubset(rec.keys())

    async def test_dispatch_card_has_call_id(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-TEST/dispatch/recommend",
            json=_recommend_body(call_id="CALL-TEST"),
            headers=AUTH_HEADER,
        )
        card = resp.json()["dispatch_card"]
        assert card["call_id"] == "CALL-TEST"

    async def test_recommendations_sorted_by_composite_score(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
            headers=AUTH_HEADER,
        )
        recs = resp.json()["recommendations"]
        scores = [r["composite_score"] for r in recs]
        assert scores == sorted(scores)

    async def test_excludes_dispatched_units(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json=_recommend_body(),
            headers=AUTH_HEADER,
        )
        recs = resp.json()["recommendations"]
        unit_ids = {r["unit_id"] for r in recs}
        assert "AMB_103" not in unit_ids

    async def test_rejects_invalid_body(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/recommend",
            json={"bad": "data"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422


class TestConfirmEndpoint:
    """POST /api/v1/calls/{call_id}/dispatch/confirm tests."""

    async def test_returns_200(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_100"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    async def test_response_has_dispatched_status(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_100"},
            headers=AUTH_HEADER,
        )
        data = resp.json()
        assert data["status"] == "dispatched"
        assert data["unit_id"] == "AMB_100"

    async def test_updates_unit_status_in_store(self, client: AsyncClient, _setup_dispatch_deps):
        deps = _setup_dispatch_deps
        await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_100"},
            headers=AUTH_HEADER,
        )
        unit = deps["store"].get_unit("AMB_100")
        assert unit is not None
        assert unit.status == "dispatched"

    async def test_sends_fcm_notification(self, client: AsyncClient, _setup_dispatch_deps):
        deps = _setup_dispatch_deps
        await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_101"},
            headers=AUTH_HEADER,
        )
        assert len(deps["fcm"].sent_notifications) == 1

    async def test_writes_audit_log(self, client: AsyncClient, _setup_dispatch_deps):
        deps = _setup_dispatch_deps
        await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={"unit_id": "AMB_102"},
            headers=AUTH_HEADER,
        )
        assert len(deps["audit"].entries) == 1
        entry = deps["audit"].entries[0]
        assert entry.event_type.value == "dispatch"

    async def test_rejects_missing_unit_id(self, client: AsyncClient, _setup_dispatch_deps):
        resp = await client.post(
            "/api/v1/calls/CALL-001/dispatch/confirm",
            json={},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422
