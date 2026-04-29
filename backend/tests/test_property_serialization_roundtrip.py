"""Property-based test for data model serialization round-trip.

Feature: crisislink-emergency-ai-copilot, Property 2: Data Model Serialization Round-Trip

Validates: Requirements 2.5, 4.6, 8.4

Uses Hypothesis to generate valid Emergency_Classification, Response_Unit, and
Dispatch_Recommendation objects, serialize to JSON, deserialize back, and assert
equivalence with all required fields preserved.
"""

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from shared.models import (
    CallerState,
    DispatchRecommendation,
    EmergencyClassification,
    Location,
    ResponseUnit,
)
from shared.models.enums import (
    CallerRole,
    EmergencyType,
    PanicLevel,
    Severity,
    UnitStatus,
    UnitType,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies for generating valid data model objects
# ---------------------------------------------------------------------------

# --- Shared strategies ---

call_id_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

# --- Emergency_Classification strategies ---

emergency_type_strategy = st.sampled_from(list(EmergencyType))
severity_strategy = st.sampled_from(list(Severity))
panic_level_strategy = st.sampled_from(list(PanicLevel))
caller_role_strategy = st.sampled_from(list(CallerRole))

caller_state_strategy = st.builds(
    CallerState,
    panic_level=panic_level_strategy,
    caller_role=caller_role_strategy,
)

language_strategy = st.sampled_from([
    "hi", "en", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa",
    "or", "as", "ur", "sa", "ne", "sd", "ks", "doi", "kok", "mai",
])

key_facts_strategy = st.lists(
    st.text(
        min_size=1,
        max_size=80,
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    ),
    min_size=0,
    max_size=10,
)

confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

timestamp_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

model_version_strategy = st.sampled_from([
    "gemini-1.5-pro-001",
    "gemini-1.5-pro-002",
    "gemini-2.0-flash",
])

classification_strategy = st.builds(
    EmergencyClassification,
    call_id=call_id_strategy,
    emergency_type=emergency_type_strategy,
    severity=severity_strategy,
    caller_state=caller_state_strategy,
    language_detected=language_strategy,
    key_facts=key_facts_strategy,
    confidence=confidence_strategy,
    timestamp=timestamp_strategy,
    model_version=model_version_strategy,
)

# --- Response_Unit strategies ---

unit_type_strategy = st.sampled_from(list(UnitType))
unit_status_strategy = st.sampled_from(list(UnitStatus))

location_strategy = st.builds(
    Location,
    lat=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    lng=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
)

unit_id_strategy = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

hospital_strategy = st.text(
    min_size=1,
    max_size=80,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
)

capabilities_strategy = st.lists(
    st.sampled_from(["cardiac", "trauma", "pediatric", "hazmat", "rescue", "fire", "general"]),
    min_size=0,
    max_size=5,
)

last_updated_strategy = st.integers(min_value=1_600_000_000, max_value=2_000_000_000)

response_unit_strategy = st.builds(
    ResponseUnit,
    unit_id=unit_id_strategy,
    type=unit_type_strategy,
    status=unit_status_strategy,
    location=location_strategy,
    hospital_or_station=hospital_strategy,
    capabilities=capabilities_strategy,
    last_updated=last_updated_strategy,
)

# --- Dispatch_Recommendation strategies ---

eta_strategy = st.floats(min_value=0.1, max_value=120.0, allow_nan=False, allow_infinity=False)
score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
distance_strategy = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
composite_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

unit_type_str_strategy = st.sampled_from(["ambulance", "fire_brigade", "police"])

dispatch_recommendation_strategy = st.builds(
    DispatchRecommendation,
    unit_id=unit_id_strategy,
    unit_type=unit_type_str_strategy,
    hospital_or_station=hospital_strategy,
    eta_minutes=eta_strategy,
    capability_match=score_strategy,
    composite_score=composite_strategy,
    distance_km=distance_strategy,
)


# ---------------------------------------------------------------------------
# Property 2: Data Model Serialization Round-Trip
# ---------------------------------------------------------------------------


class TestDataModelSerializationRoundTrip:
    """Property 2: Data Model Serialization Round-Trip

    For any valid data model object (Emergency_Classification, Response_Unit,
    or Dispatch_Recommendation), serializing the object to JSON and then
    deserializing the JSON back SHALL produce an object equivalent to the
    original, with all required fields preserved.

    **Validates: Requirements 2.5, 4.6, 8.4**
    """

    # --- Emergency_Classification round-trip ---

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_emergency_classification_json_roundtrip(
        self, classification: EmergencyClassification
    ):
        """Serializing an Emergency_Classification to JSON and deserializing
        back produces an equivalent object.

        **Validates: Requirements 2.5**
        """
        json_str = classification.model_dump_json()
        restored = EmergencyClassification.model_validate_json(json_str)

        assert restored == classification

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_emergency_classification_dict_roundtrip(
        self, classification: EmergencyClassification
    ):
        """Serializing an Emergency_Classification to dict and back preserves
        all required fields.

        **Validates: Requirements 2.5**
        """
        data = classification.model_dump()
        restored = EmergencyClassification.model_validate(data)

        assert restored.call_id == classification.call_id
        assert restored.emergency_type == classification.emergency_type
        assert restored.severity == classification.severity
        assert restored.caller_state == classification.caller_state
        assert restored.language_detected == classification.language_detected
        assert restored.key_facts == classification.key_facts
        assert restored.confidence == classification.confidence
        assert restored.timestamp == classification.timestamp
        assert restored.model_version == classification.model_version

    # --- Response_Unit round-trip ---

    @given(unit=response_unit_strategy)
    @settings(max_examples=200)
    def test_response_unit_json_roundtrip(self, unit: ResponseUnit):
        """Serializing a Response_Unit to JSON and deserializing back produces
        an equivalent object.

        **Validates: Requirements 8.4**
        """
        json_str = unit.model_dump_json()
        restored = ResponseUnit.model_validate_json(json_str)

        assert restored == unit

    @given(unit=response_unit_strategy)
    @settings(max_examples=200)
    def test_response_unit_dict_roundtrip(self, unit: ResponseUnit):
        """Serializing a Response_Unit to dict and back preserves all required
        fields.

        **Validates: Requirements 8.4**
        """
        data = unit.model_dump()
        restored = ResponseUnit.model_validate(data)

        assert restored.unit_id == unit.unit_id
        assert restored.type == unit.type
        assert restored.status == unit.status
        assert restored.location == unit.location
        assert restored.hospital_or_station == unit.hospital_or_station
        assert restored.capabilities == unit.capabilities
        assert restored.last_updated == unit.last_updated

    # --- Dispatch_Recommendation round-trip ---

    @given(rec=dispatch_recommendation_strategy)
    @settings(max_examples=200)
    def test_dispatch_recommendation_json_roundtrip(
        self, rec: DispatchRecommendation
    ):
        """Serializing a Dispatch_Recommendation to JSON and deserializing back
        produces an equivalent object.

        **Validates: Requirements 4.6**
        """
        json_str = rec.model_dump_json()
        restored = DispatchRecommendation.model_validate_json(json_str)

        assert restored == rec

    @given(rec=dispatch_recommendation_strategy)
    @settings(max_examples=200)
    def test_dispatch_recommendation_dict_roundtrip(
        self, rec: DispatchRecommendation
    ):
        """Serializing a Dispatch_Recommendation to dict and back preserves all
        required fields.

        **Validates: Requirements 4.6**
        """
        data = rec.model_dump()
        restored = DispatchRecommendation.model_validate(data)

        assert restored.unit_id == rec.unit_id
        assert restored.unit_type == rec.unit_type
        assert restored.hospital_or_station == rec.hospital_or_station
        assert restored.eta_minutes == rec.eta_minutes
        assert restored.capability_match == rec.capability_match
        assert restored.composite_score == rec.composite_score
        assert restored.distance_km == rec.distance_km
