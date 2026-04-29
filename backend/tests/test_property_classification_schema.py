"""Property-based test for Emergency_Classification schema validation.

Feature: crisislink-emergency-ai-copilot, Property 1: Emergency_Classification Schema Validation

Validates: Requirements 2.1, 2.2, 2.3, 2.5, 3.1, 3.2

Uses Hypothesis to generate random Emergency_Classification JSON objects and
validate that all required fields exist with values from allowed enum sets.
"""

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from shared.models import (
    CallerState,
    EmergencyClassification,
)
from shared.models.enums import (
    CallerRole,
    EmergencyType,
    PanicLevel,
    Severity,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies for generating valid Emergency_Classification data
# ---------------------------------------------------------------------------

emergency_type_strategy = st.sampled_from(list(EmergencyType))
severity_strategy = st.sampled_from(list(Severity))
panic_level_strategy = st.sampled_from(list(PanicLevel))
caller_role_strategy = st.sampled_from(list(CallerRole))

caller_state_strategy = st.builds(
    CallerState,
    panic_level=panic_level_strategy,
    caller_role=caller_role_strategy,
)

# ISO 639-1 language codes commonly used in India
language_strategy = st.sampled_from([
    "hi", "en", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa",
    "or", "as", "ur", "sa", "ne", "sd", "ks", "doi", "kok", "mai",
    "bho", "mni",
])

key_facts_strategy = st.lists(
    st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
    )),
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

call_id_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=("L", "N"),
    whitelist_characters="-_",
))

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


# ---------------------------------------------------------------------------
# Property 1: Emergency_Classification Schema Validation
# ---------------------------------------------------------------------------


class TestEmergencyClassificationSchemaValidation:
    """Property 1: Emergency_Classification Schema Validation

    For any JSON object produced by the Intelligence Engine as an
    Emergency_Classification, the object SHALL contain all required fields
    and each enum field SHALL contain only values from its allowed set.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.5, 3.1, 3.2**
    """

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_all_required_fields_exist(self, classification: EmergencyClassification):
        """Every generated Emergency_Classification has all required fields.

        **Validates: Requirements 2.1, 2.5**
        """
        json_dict = classification.model_dump()

        # All top-level required fields must be present
        assert "emergency_type" in json_dict
        assert "severity" in json_dict
        assert "caller_state" in json_dict
        assert "language_detected" in json_dict
        assert "key_facts" in json_dict
        assert "confidence" in json_dict

        # Nested caller_state required fields
        assert "panic_level" in json_dict["caller_state"]
        assert "caller_role" in json_dict["caller_state"]

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_emergency_type_in_allowed_set(self, classification: EmergencyClassification):
        """emergency_type is always from {MEDICAL, FIRE, CRIME, ACCIDENT, DISASTER, UNKNOWN}.

        **Validates: Requirements 2.2**
        """
        allowed = {"MEDICAL", "FIRE", "CRIME", "ACCIDENT", "DISASTER", "UNKNOWN"}
        assert classification.emergency_type.value in allowed

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_severity_in_allowed_set(self, classification: EmergencyClassification):
        """severity is always from {CRITICAL, HIGH, MODERATE, LOW}.

        **Validates: Requirements 2.3**
        """
        allowed = {"CRITICAL", "HIGH", "MODERATE", "LOW"}
        assert classification.severity.value in allowed

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_panic_level_in_allowed_set(self, classification: EmergencyClassification):
        """caller_state.panic_level is always from {PANIC_HIGH, PANIC_MED, CALM, INCOHERENT}.

        **Validates: Requirements 3.1**
        """
        allowed = {"PANIC_HIGH", "PANIC_MED", "CALM", "INCOHERENT"}
        assert classification.caller_state.panic_level.value in allowed

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_caller_role_in_allowed_set(self, classification: EmergencyClassification):
        """caller_state.caller_role is always from {VICTIM, BYSTANDER, WITNESS}.

        **Validates: Requirements 3.2**
        """
        allowed = {"VICTIM", "BYSTANDER", "WITNESS"}
        assert classification.caller_state.caller_role.value in allowed

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_confidence_is_float_in_valid_range(self, classification: EmergencyClassification):
        """confidence is always a float in [0.0, 1.0].

        **Validates: Requirements 2.1**
        """
        assert isinstance(classification.confidence, float)
        assert 0.0 <= classification.confidence <= 1.0

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_key_facts_is_list_of_strings(self, classification: EmergencyClassification):
        """key_facts is always a list of strings.

        **Validates: Requirements 2.1**
        """
        assert isinstance(classification.key_facts, list)
        for fact in classification.key_facts:
            assert isinstance(fact, str)

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_serialized_json_preserves_enum_values(self, classification: EmergencyClassification):
        """Serialized JSON contains valid enum string values, not arbitrary strings.

        **Validates: Requirements 2.5**
        """
        json_dict = classification.model_dump()

        # Verify serialized enum values match allowed sets
        emergency_types = {e.value for e in EmergencyType}
        severities = {s.value for s in Severity}
        panic_levels = {p.value for p in PanicLevel}
        caller_roles = {r.value for r in CallerRole}

        assert json_dict["emergency_type"] in emergency_types
        assert json_dict["severity"] in severities
        assert json_dict["caller_state"]["panic_level"] in panic_levels
        assert json_dict["caller_state"]["caller_role"] in caller_roles

    @given(classification=classification_strategy)
    @settings(max_examples=200)
    def test_json_roundtrip_preserves_all_fields(self, classification: EmergencyClassification):
        """Serializing to JSON and deserializing back preserves all required fields and values.

        **Validates: Requirements 2.5**
        """
        json_str = classification.model_dump_json()
        restored = EmergencyClassification.model_validate_json(json_str)

        assert restored.emergency_type == classification.emergency_type
        assert restored.severity == classification.severity
        assert restored.caller_state.panic_level == classification.caller_state.panic_level
        assert restored.caller_state.caller_role == classification.caller_state.caller_role
        assert restored.language_detected == classification.language_detected
        assert restored.key_facts == classification.key_facts
        assert restored.confidence == classification.confidence
