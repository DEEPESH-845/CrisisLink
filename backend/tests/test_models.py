"""Unit tests for CrisisLink core Pydantic data models."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.models import (
    AuditEventType,
    AuditLogEntry,
    CallerRole,
    CallerState,
    CallSession,
    CallStatus,
    DispatchCard,
    DispatchRecommendation,
    EmergencyClassification,
    EmergencyType,
    Guidance,
    GuidanceStatus,
    Location,
    PanicLevel,
    ResponseUnit,
    Severity,
    UnitStatus,
    UnitType,
)


# ---------------------------------------------------------------------------
# Emergency Classification
# ---------------------------------------------------------------------------


class TestEmergencyClassification:
    """Tests for EmergencyClassification model."""

    def _make_classification(self, **overrides):
        defaults = {
            "call_id": "CALL-001",
            "emergency_type": EmergencyType.MEDICAL,
            "severity": Severity.CRITICAL,
            "caller_state": {
                "panic_level": PanicLevel.PANIC_HIGH,
                "caller_role": CallerRole.VICTIM,
            },
            "language_detected": "hi",
            "key_facts": ["chest pain", "male", "age 55"],
            "confidence": 0.92,
            "timestamp": "2025-01-15T10:30:00Z",
            "model_version": "gemini-1.5-pro-001",
        }
        defaults.update(overrides)
        return EmergencyClassification(**defaults)

    def test_valid_classification(self):
        ec = self._make_classification()
        assert ec.call_id == "CALL-001"
        assert ec.emergency_type == EmergencyType.MEDICAL
        assert ec.severity == Severity.CRITICAL
        assert ec.caller_state.panic_level == PanicLevel.PANIC_HIGH
        assert ec.caller_state.caller_role == CallerRole.VICTIM
        assert ec.language_detected == "hi"
        assert ec.key_facts == ["chest pain", "male", "age 55"]
        assert ec.confidence == 0.92
        assert ec.model_version == "gemini-1.5-pro-001"

    def test_all_emergency_types(self):
        for etype in EmergencyType:
            ec = self._make_classification(emergency_type=etype)
            assert ec.emergency_type == etype

    def test_all_severity_levels(self):
        for sev in Severity:
            ec = self._make_classification(severity=sev)
            assert ec.severity == sev

    def test_confidence_boundary_zero(self):
        ec = self._make_classification(confidence=0.0)
        assert ec.confidence == 0.0

    def test_confidence_boundary_one(self):
        ec = self._make_classification(confidence=1.0)
        assert ec.confidence == 1.0

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            self._make_classification(confidence=-0.01)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            self._make_classification(confidence=1.01)

    def test_invalid_emergency_type_rejected(self):
        with pytest.raises(ValidationError):
            self._make_classification(emergency_type="EARTHQUAKE")

    def test_empty_key_facts(self):
        ec = self._make_classification(key_facts=[])
        assert ec.key_facts == []

    def test_serialization_roundtrip(self):
        ec = self._make_classification()
        json_str = ec.model_dump_json()
        restored = EmergencyClassification.model_validate_json(json_str)
        assert restored == ec


# ---------------------------------------------------------------------------
# Response Unit
# ---------------------------------------------------------------------------


class TestResponseUnit:
    """Tests for ResponseUnit model."""

    def _make_unit(self, **overrides):
        defaults = {
            "unit_id": "AMB_007",
            "type": UnitType.AMBULANCE,
            "status": UnitStatus.AVAILABLE,
            "location": {"lat": 28.6139, "lng": 77.2090},
            "hospital_or_station": "AIIMS Delhi",
            "capabilities": ["cardiac", "trauma"],
            "last_updated": 1705312200,
        }
        defaults.update(overrides)
        return ResponseUnit(**defaults)

    def test_valid_unit(self):
        unit = self._make_unit()
        assert unit.unit_id == "AMB_007"
        assert unit.type == UnitType.AMBULANCE
        assert unit.status == UnitStatus.AVAILABLE
        assert unit.location.lat == 28.6139
        assert unit.location.lng == 77.2090
        assert unit.hospital_or_station == "AIIMS Delhi"
        assert "cardiac" in unit.capabilities

    def test_all_unit_types(self):
        for utype in UnitType:
            unit = self._make_unit(type=utype)
            assert unit.type == utype

    def test_all_unit_statuses(self):
        for status in UnitStatus:
            unit = self._make_unit(status=status)
            assert unit.status == status

    def test_empty_capabilities(self):
        unit = self._make_unit(capabilities=[])
        assert unit.capabilities == []

    def test_serialization_roundtrip(self):
        unit = self._make_unit()
        json_str = unit.model_dump_json()
        restored = ResponseUnit.model_validate_json(json_str)
        assert restored == unit


# ---------------------------------------------------------------------------
# Dispatch Recommendation & Card
# ---------------------------------------------------------------------------


class TestDispatchRecommendation:
    """Tests for DispatchRecommendation model."""

    def _make_recommendation(self, **overrides):
        defaults = {
            "unit_id": "AMB_007",
            "unit_type": "ambulance",
            "hospital_or_station": "AIIMS Delhi",
            "eta_minutes": 8.5,
            "capability_match": 0.95,
            "composite_score": 0.72,
            "distance_km": 5.3,
        }
        defaults.update(overrides)
        return DispatchRecommendation(**defaults)

    def test_valid_recommendation(self):
        rec = self._make_recommendation()
        assert rec.unit_id == "AMB_007"
        assert rec.eta_minutes == 8.5
        assert rec.capability_match == 0.95
        assert rec.composite_score == 0.72
        assert rec.distance_km == 5.3

    def test_capability_match_boundary_zero(self):
        rec = self._make_recommendation(capability_match=0.0)
        assert rec.capability_match == 0.0

    def test_capability_match_boundary_one(self):
        rec = self._make_recommendation(capability_match=1.0)
        assert rec.capability_match == 1.0

    def test_capability_match_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            self._make_recommendation(capability_match=-0.1)

    def test_capability_match_above_one_rejected(self):
        with pytest.raises(ValidationError):
            self._make_recommendation(capability_match=1.1)

    def test_serialization_roundtrip(self):
        rec = self._make_recommendation()
        json_str = rec.model_dump_json()
        restored = DispatchRecommendation.model_validate_json(json_str)
        assert restored == rec


class TestDispatchCard:
    """Tests for DispatchCard model."""

    def test_valid_dispatch_card(self):
        card = DispatchCard(
            call_id="CALL-001",
            recommendations=[
                DispatchRecommendation(
                    unit_id="AMB_007",
                    unit_type="ambulance",
                    hospital_or_station="AIIMS Delhi",
                    eta_minutes=8.5,
                    capability_match=0.95,
                    composite_score=0.72,
                    distance_km=5.3,
                ),
            ],
            generated_at="2025-01-15T10:31:00Z",
            classification_ref="CLASS-001",
        )
        assert card.call_id == "CALL-001"
        assert len(card.recommendations) == 1
        assert card.classification_ref == "CLASS-001"

    def test_empty_recommendations(self):
        card = DispatchCard(
            call_id="CALL-002",
            recommendations=[],
            generated_at="2025-01-15T10:31:00Z",
            classification_ref="CLASS-002",
        )
        assert card.recommendations == []

    def test_serialization_roundtrip(self):
        card = DispatchCard(
            call_id="CALL-001",
            recommendations=[
                DispatchRecommendation(
                    unit_id="AMB_007",
                    unit_type="ambulance",
                    hospital_or_station="AIIMS Delhi",
                    eta_minutes=8.5,
                    capability_match=0.95,
                    composite_score=0.72,
                    distance_km=5.3,
                ),
            ],
            generated_at="2025-01-15T10:31:00Z",
            classification_ref="CLASS-001",
        )
        json_str = card.model_dump_json()
        restored = DispatchCard.model_validate_json(json_str)
        assert restored == card


# ---------------------------------------------------------------------------
# Call Session
# ---------------------------------------------------------------------------


class TestCallSession:
    """Tests for CallSession model."""

    def test_minimal_call_session(self):
        session = CallSession(
            call_id="CALL-001",
            status=CallStatus.ACTIVE,
            started_at="2025-01-15T10:30:00Z",
            updated_at="2025-01-15T10:30:00Z",
        )
        assert session.call_id == "CALL-001"
        assert session.status == CallStatus.ACTIVE
        assert session.classification is None
        assert session.caller_state is None
        assert session.dispatch_card is None
        assert session.confirmed_unit is None
        assert session.guidance is None
        assert session.manual_override is False
        assert session.transcript == ""

    def test_full_call_session(self):
        session = CallSession(
            call_id="CALL-001",
            status=CallStatus.DISPATCHED,
            transcript="Help, there is a fire!",
            classification=EmergencyClassification(
                call_id="CALL-001",
                emergency_type=EmergencyType.FIRE,
                severity=Severity.HIGH,
                caller_state=CallerState(
                    panic_level=PanicLevel.PANIC_HIGH,
                    caller_role=CallerRole.BYSTANDER,
                ),
                language_detected="en",
                key_facts=["fire", "building"],
                confidence=0.88,
                timestamp="2025-01-15T10:30:05Z",
                model_version="gemini-1.5-pro-001",
            ),
            caller_state=CallerState(
                panic_level=PanicLevel.PANIC_HIGH,
                caller_role=CallerRole.BYSTANDER,
            ),
            dispatch_card=DispatchCard(
                call_id="CALL-001",
                recommendations=[],
                generated_at="2025-01-15T10:30:07Z",
                classification_ref="CLASS-001",
            ),
            confirmed_unit="FB_003",
            guidance=Guidance(
                status=GuidanceStatus.ACTIVE,
                language="en",
                protocol_type="FIRE_NDMA",
            ),
            manual_override=False,
            started_at="2025-01-15T10:30:00Z",
            updated_at="2025-01-15T10:30:10Z",
        )
        assert session.status == CallStatus.DISPATCHED
        assert session.classification is not None
        assert session.classification.emergency_type == EmergencyType.FIRE
        assert session.confirmed_unit == "FB_003"
        assert session.guidance.protocol_type == "FIRE_NDMA"

    def test_all_call_statuses(self):
        for status in CallStatus:
            session = CallSession(
                call_id="CALL-001",
                status=status,
                started_at="2025-01-15T10:30:00Z",
                updated_at="2025-01-15T10:30:00Z",
            )
            assert session.status == status

    def test_all_guidance_statuses(self):
        for gs in GuidanceStatus:
            guidance = Guidance(
                status=gs, language="hi", protocol_type="CPR_IRC_2022"
            )
            assert guidance.status == gs

    def test_serialization_roundtrip(self):
        session = CallSession(
            call_id="CALL-001",
            status=CallStatus.ACTIVE,
            started_at="2025-01-15T10:30:00Z",
            updated_at="2025-01-15T10:30:00Z",
        )
        json_str = session.model_dump_json()
        restored = CallSession.model_validate_json(json_str)
        assert restored == session


# ---------------------------------------------------------------------------
# Audit Log Entry
# ---------------------------------------------------------------------------


class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""

    def test_valid_audit_entry(self):
        entry = AuditLogEntry(
            log_id="LOG-001",
            call_id="CALL-001",
            event_type=AuditEventType.CLASSIFICATION,
            payload={"emergency_type": "MEDICAL", "confidence": 0.92},
            actor="intelligence-engine",
            timestamp="2025-01-15T10:30:05Z",
        )
        assert entry.log_id == "LOG-001"
        assert entry.event_type == AuditEventType.CLASSIFICATION
        assert entry.payload["confidence"] == 0.92
        assert entry.actor == "intelligence-engine"

    def test_all_event_types(self):
        for etype in AuditEventType:
            entry = AuditLogEntry(
                log_id="LOG-001",
                call_id="CALL-001",
                event_type=etype,
                payload={},
                actor="system",
                timestamp="2025-01-15T10:30:05Z",
            )
            assert entry.event_type == etype

    def test_empty_payload(self):
        entry = AuditLogEntry(
            log_id="LOG-002",
            call_id="CALL-001",
            event_type=AuditEventType.ERROR,
            payload={},
            actor="dispatch-engine",
            timestamp="2025-01-15T10:30:05Z",
        )
        assert entry.payload == {}

    def test_serialization_roundtrip(self):
        entry = AuditLogEntry(
            log_id="LOG-001",
            call_id="CALL-001",
            event_type=AuditEventType.DISPATCH,
            payload={"unit_id": "AMB_007"},
            actor="operator-42",
            timestamp="2025-01-15T10:30:05Z",
        )
        json_str = entry.model_dump_json()
        restored = AuditLogEntry.model_validate_json(json_str)
        assert restored == entry
