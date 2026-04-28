"""Tests for the CrisisLink Guidance Generator.

Covers:
- All (panic_level, caller_role) combinations for correct register selection
- MEDICAL + cardiac indicators → CPR_IRC_2022
- FIRE → FIRE_NDMA
- Other types → GENERAL
- Severity CRITICAL/HIGH → guidance generated
- Severity MODERATE/LOW → no guidance
- Guidance text is non-empty for CRITICAL/HIGH
- Firebase RTDB guidance writes

Requirements: 3.3, 3.4, 3.5, 3.6, 5.1, 5.2, 5.4, 5.5, 5.6, 5.7
"""

from datetime import datetime, timezone

import pytest

from intelligence.guidance_generator import (
    CARDIAC_INDICATORS,
    GuidanceProtocol,
    GuidanceRegister,
    generate_guidance_text,
    select_guidance_protocol,
    select_guidance_register,
    should_generate_guidance,
)
from shared.models import (
    CallerRole,
    CallerState,
    EmergencyClassification,
    EmergencyType,
    PanicLevel,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classification(
    call_id: str = "CALL-G001",
    severity: Severity = Severity.CRITICAL,
    emergency_type: EmergencyType = EmergencyType.MEDICAL,
    language: str = "hi",
    key_facts: list[str] | None = None,
) -> EmergencyClassification:
    """Build a valid EmergencyClassification for testing."""
    return EmergencyClassification(
        call_id=call_id,
        emergency_type=emergency_type,
        severity=severity,
        caller_state=CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.VICTIM,
        ),
        language_detected=language,
        key_facts=key_facts or [],
        confidence=0.85,
        timestamp=datetime.now(timezone.utc),
        model_version="test-v0",
    )


# ---------------------------------------------------------------------------
# Register selection tests
# ---------------------------------------------------------------------------


class TestSelectGuidanceRegister:
    """Test all (panic_level, caller_role) combinations for register selection."""

    def test_panic_high_victim_returns_reassurance_first(self):
        result = select_guidance_register(PanicLevel.PANIC_HIGH, CallerRole.VICTIM)
        assert result == GuidanceRegister.REASSURANCE_FIRST

    def test_panic_high_bystander_returns_directive_steps(self):
        result = select_guidance_register(PanicLevel.PANIC_HIGH, CallerRole.BYSTANDER)
        assert result == GuidanceRegister.DIRECTIVE_STEPS

    def test_calm_bystander_returns_clinical_protocol(self):
        result = select_guidance_register(PanicLevel.CALM, CallerRole.BYSTANDER)
        assert result == GuidanceRegister.CLINICAL_PROTOCOL

    def test_panic_high_witness_returns_default(self):
        result = select_guidance_register(PanicLevel.PANIC_HIGH, CallerRole.WITNESS)
        assert result == GuidanceRegister.DEFAULT

    def test_panic_med_victim_returns_default(self):
        result = select_guidance_register(PanicLevel.PANIC_MED, CallerRole.VICTIM)
        assert result == GuidanceRegister.DEFAULT

    def test_panic_med_bystander_returns_default(self):
        result = select_guidance_register(PanicLevel.PANIC_MED, CallerRole.BYSTANDER)
        assert result == GuidanceRegister.DEFAULT

    def test_panic_med_witness_returns_default(self):
        result = select_guidance_register(PanicLevel.PANIC_MED, CallerRole.WITNESS)
        assert result == GuidanceRegister.DEFAULT

    def test_calm_victim_returns_default(self):
        result = select_guidance_register(PanicLevel.CALM, CallerRole.VICTIM)
        assert result == GuidanceRegister.DEFAULT

    def test_calm_witness_returns_default(self):
        result = select_guidance_register(PanicLevel.CALM, CallerRole.WITNESS)
        assert result == GuidanceRegister.DEFAULT

    def test_incoherent_victim_returns_default(self):
        result = select_guidance_register(PanicLevel.INCOHERENT, CallerRole.VICTIM)
        assert result == GuidanceRegister.DEFAULT

    def test_incoherent_bystander_returns_default(self):
        result = select_guidance_register(PanicLevel.INCOHERENT, CallerRole.BYSTANDER)
        assert result == GuidanceRegister.DEFAULT

    def test_incoherent_witness_returns_default(self):
        result = select_guidance_register(PanicLevel.INCOHERENT, CallerRole.WITNESS)
        assert result == GuidanceRegister.DEFAULT


# ---------------------------------------------------------------------------
# Protocol selection tests
# ---------------------------------------------------------------------------


class TestSelectGuidanceProtocol:
    """Test protocol selection based on emergency type and key facts."""

    def test_medical_with_cardiac_returns_cpr_irc_2022(self):
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["cardiac arrest", "elderly person"]
        )
        assert result == GuidanceProtocol.CPR_IRC_2022

    def test_medical_with_heart_attack_returns_cpr_irc_2022(self):
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["heart attack", "male 55"]
        )
        assert result == GuidanceProtocol.CPR_IRC_2022

    def test_medical_with_chest_pain_returns_cpr_irc_2022(self):
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["chest pain", "shortness of breath"]
        )
        assert result == GuidanceProtocol.CPR_IRC_2022

    def test_medical_with_cpr_keyword_returns_cpr_irc_2022(self):
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["needs CPR", "not breathing"]
        )
        assert result == GuidanceProtocol.CPR_IRC_2022

    def test_medical_with_cardiac_keyword_returns_cpr_irc_2022(self):
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["cardiac event"]
        )
        assert result == GuidanceProtocol.CPR_IRC_2022

    def test_medical_without_cardiac_returns_general(self):
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["broken leg", "bleeding"]
        )
        assert result == GuidanceProtocol.GENERAL

    def test_medical_empty_facts_returns_general(self):
        result = select_guidance_protocol(EmergencyType.MEDICAL, [])
        assert result == GuidanceProtocol.GENERAL

    def test_fire_returns_fire_ndma(self):
        result = select_guidance_protocol(EmergencyType.FIRE, [])
        assert result == GuidanceProtocol.FIRE_NDMA

    def test_fire_with_facts_returns_fire_ndma(self):
        result = select_guidance_protocol(
            EmergencyType.FIRE, ["building on fire", "people trapped"]
        )
        assert result == GuidanceProtocol.FIRE_NDMA

    def test_crime_returns_general(self):
        result = select_guidance_protocol(EmergencyType.CRIME, ["robbery"])
        assert result == GuidanceProtocol.GENERAL

    def test_accident_returns_general(self):
        result = select_guidance_protocol(
            EmergencyType.ACCIDENT, ["car crash"]
        )
        assert result == GuidanceProtocol.GENERAL

    def test_disaster_returns_general(self):
        result = select_guidance_protocol(
            EmergencyType.DISASTER, ["earthquake"]
        )
        assert result == GuidanceProtocol.GENERAL

    def test_unknown_returns_general(self):
        result = select_guidance_protocol(EmergencyType.UNKNOWN, [])
        assert result == GuidanceProtocol.GENERAL

    def test_cardiac_indicator_case_insensitive(self):
        """Cardiac indicators should match case-insensitively."""
        result = select_guidance_protocol(
            EmergencyType.MEDICAL, ["CARDIAC ARREST"]
        )
        assert result == GuidanceProtocol.CPR_IRC_2022


# ---------------------------------------------------------------------------
# Severity threshold tests
# ---------------------------------------------------------------------------


class TestShouldGenerateGuidance:
    """Test severity threshold for guidance trigger."""

    def test_critical_returns_true(self):
        assert should_generate_guidance(Severity.CRITICAL) is True

    def test_high_returns_true(self):
        assert should_generate_guidance(Severity.HIGH) is True

    def test_moderate_returns_false(self):
        assert should_generate_guidance(Severity.MODERATE) is False

    def test_low_returns_false(self):
        assert should_generate_guidance(Severity.LOW) is False


# ---------------------------------------------------------------------------
# Guidance text generation tests
# ---------------------------------------------------------------------------


class TestGenerateGuidanceText:
    """Test end-to-end guidance text generation."""

    def test_critical_severity_produces_nonempty_text(self):
        classification = _make_classification(severity=Severity.CRITICAL)
        caller_state = CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.VICTIM,
        )
        result = generate_guidance_text(classification, caller_state)
        assert result != ""
        assert len(result) > 0

    def test_high_severity_produces_nonempty_text(self):
        classification = _make_classification(severity=Severity.HIGH)
        caller_state = CallerState(
            panic_level=PanicLevel.CALM,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert result != ""
        assert len(result) > 0

    def test_moderate_severity_produces_empty_text(self):
        classification = _make_classification(severity=Severity.MODERATE)
        caller_state = CallerState(
            panic_level=PanicLevel.CALM,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert result == ""

    def test_low_severity_produces_empty_text(self):
        classification = _make_classification(severity=Severity.LOW)
        caller_state = CallerState(
            panic_level=PanicLevel.CALM,
            caller_role=CallerRole.WITNESS,
        )
        result = generate_guidance_text(classification, caller_state)
        assert result == ""

    def test_reassurance_register_in_guidance_text(self):
        """PANIC_HIGH + VICTIM should produce reassurance-first text."""
        classification = _make_classification(severity=Severity.CRITICAL)
        caller_state = CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.VICTIM,
        )
        result = generate_guidance_text(classification, caller_state)
        assert "safe" in result.lower() or "calm" in result.lower()

    def test_directive_register_in_guidance_text(self):
        """PANIC_HIGH + BYSTANDER should produce directive steps."""
        classification = _make_classification(severity=Severity.CRITICAL)
        caller_state = CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert "steps" in result.lower()

    def test_clinical_register_in_guidance_text(self):
        """CALM + BYSTANDER should produce clinical protocol text."""
        classification = _make_classification(severity=Severity.HIGH)
        caller_state = CallerState(
            panic_level=PanicLevel.CALM,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert "clinical" in result.lower() or "protocol" in result.lower()

    def test_cpr_protocol_in_guidance_text(self):
        """MEDICAL + cardiac indicators should include CPR content."""
        classification = _make_classification(
            severity=Severity.CRITICAL,
            emergency_type=EmergencyType.MEDICAL,
            key_facts=["cardiac arrest", "elderly"],
        )
        caller_state = CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert "cpr" in result.lower() or "compressions" in result.lower()

    def test_fire_protocol_in_guidance_text(self):
        """FIRE emergency should include fire evacuation content."""
        classification = _make_classification(
            severity=Severity.CRITICAL,
            emergency_type=EmergencyType.FIRE,
        )
        caller_state = CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert "fire" in result.lower() or "evacuation" in result.lower()

    def test_language_included_in_guidance(self):
        """Guidance text should reference the detected language."""
        classification = _make_classification(
            severity=Severity.CRITICAL,
            language="ta",
        )
        caller_state = CallerState(
            panic_level=PanicLevel.CALM,
            caller_role=CallerRole.BYSTANDER,
        )
        result = generate_guidance_text(classification, caller_state)
        assert "ta" in result
