"""Property-based test for severity threshold for guidance trigger.

Feature: crisislink-emergency-ai-copilot, Property 8: Severity Threshold for Guidance Trigger

Validates: Requirements 5.1

Uses Hypothesis to generate random severity enum values and verify:
- CRITICAL or HIGH → guidance generated (should_generate_guidance returns True)
- MODERATE or LOW → no guidance (should_generate_guidance returns False)

Also verifies the end-to-end behaviour via generate_guidance_text:
- CRITICAL or HIGH → non-empty guidance text
- MODERATE or LOW → empty string
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from intelligence.guidance_generator import (
    generate_guidance_text,
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
# Hypothesis strategies
# ---------------------------------------------------------------------------

severity_strategy = st.sampled_from(list(Severity))

# Severities that SHOULD trigger guidance
high_severity_strategy = st.sampled_from([Severity.CRITICAL, Severity.HIGH])

# Severities that should NOT trigger guidance
low_severity_strategy = st.sampled_from([Severity.MODERATE, Severity.LOW])

# Supporting strategies for building full classifications
emergency_type_strategy = st.sampled_from(list(EmergencyType))
panic_level_strategy = st.sampled_from(list(PanicLevel))
caller_role_strategy = st.sampled_from(list(CallerRole))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classification(
    severity: Severity,
    emergency_type: EmergencyType = EmergencyType.MEDICAL,
    panic_level: PanicLevel = PanicLevel.CALM,
    caller_role: CallerRole = CallerRole.BYSTANDER,
) -> tuple[EmergencyClassification, CallerState]:
    """Build a valid EmergencyClassification and CallerState for testing."""
    caller_state = CallerState(
        panic_level=panic_level,
        caller_role=caller_role,
    )
    classification = EmergencyClassification(
        call_id="CALL-PBT-SEV",
        emergency_type=emergency_type,
        severity=severity,
        caller_state=caller_state,
        language_detected="hi",
        key_facts=["test fact"],
        confidence=0.9,
        timestamp=datetime.now(timezone.utc),
        model_version="test-v0",
    )
    return classification, caller_state


# ---------------------------------------------------------------------------
# Property 8: Severity Threshold for Guidance Trigger
# ---------------------------------------------------------------------------


class TestSeverityThresholdForGuidanceTrigger:
    """Property 8: Severity Threshold for Guidance Trigger

    For any Emergency_Classification, the Guidance Generator SHALL begin
    generating caller instructions if and only if the severity is CRITICAL
    or HIGH. Classifications with severity MODERATE or LOW SHALL NOT
    trigger guidance generation.

    **Validates: Requirements 5.1**
    """

    @given(severity=severity_strategy)
    @settings(max_examples=200)
    def test_should_generate_guidance_matches_severity_rule(
        self,
        severity: Severity,
    ) -> None:
        """For any severity enum value, should_generate_guidance returns True
        only for CRITICAL or HIGH, and False for MODERATE or LOW.

        **Validates: Requirements 5.1**
        """
        result = should_generate_guidance(severity)
        if severity in (Severity.CRITICAL, Severity.HIGH):
            assert result is True, (
                f"Expected guidance to be generated for severity={severity.value}, "
                f"but should_generate_guidance returned False"
            )
        else:
            assert result is False, (
                f"Expected no guidance for severity={severity.value}, "
                f"but should_generate_guidance returned True"
            )

    @given(severity=high_severity_strategy)
    @settings(max_examples=200)
    def test_critical_or_high_always_triggers_guidance(
        self,
        severity: Severity,
    ) -> None:
        """CRITICAL and HIGH severity always trigger guidance generation.

        **Validates: Requirements 5.1**
        """
        assert should_generate_guidance(severity) is True, (
            f"severity={severity.value} should trigger guidance"
        )

    @given(severity=low_severity_strategy)
    @settings(max_examples=200)
    def test_moderate_or_low_never_triggers_guidance(
        self,
        severity: Severity,
    ) -> None:
        """MODERATE and LOW severity never trigger guidance generation.

        **Validates: Requirements 5.1**
        """
        assert should_generate_guidance(severity) is False, (
            f"severity={severity.value} should not trigger guidance"
        )

    @given(
        severity=high_severity_strategy,
        emergency_type=emergency_type_strategy,
        panic_level=panic_level_strategy,
        caller_role=caller_role_strategy,
    )
    @settings(max_examples=200)
    def test_generate_guidance_text_nonempty_for_high_severity(
        self,
        severity: Severity,
        emergency_type: EmergencyType,
        panic_level: PanicLevel,
        caller_role: CallerRole,
    ) -> None:
        """For any CRITICAL or HIGH severity, generate_guidance_text produces
        a non-empty string regardless of other classification parameters.

        **Validates: Requirements 5.1**
        """
        classification, caller_state = _make_classification(
            severity=severity,
            emergency_type=emergency_type,
            panic_level=panic_level,
            caller_role=caller_role,
        )
        result = generate_guidance_text(classification, caller_state)
        assert result != "", (
            f"Expected non-empty guidance for severity={severity.value}, "
            f"emergency_type={emergency_type.value}, "
            f"panic_level={panic_level.value}, caller_role={caller_role.value}"
        )

    @given(
        severity=low_severity_strategy,
        emergency_type=emergency_type_strategy,
        panic_level=panic_level_strategy,
        caller_role=caller_role_strategy,
    )
    @settings(max_examples=200)
    def test_generate_guidance_text_empty_for_low_severity(
        self,
        severity: Severity,
        emergency_type: EmergencyType,
        panic_level: PanicLevel,
        caller_role: CallerRole,
    ) -> None:
        """For any MODERATE or LOW severity, generate_guidance_text returns
        an empty string regardless of other classification parameters.

        **Validates: Requirements 5.1**
        """
        classification, caller_state = _make_classification(
            severity=severity,
            emergency_type=emergency_type,
            panic_level=panic_level,
            caller_role=caller_role,
        )
        result = generate_guidance_text(classification, caller_state)
        assert result == "", (
            f"Expected empty guidance for severity={severity.value}, "
            f"emergency_type={emergency_type.value}, "
            f"panic_level={panic_level.value}, caller_role={caller_role.value}, "
            f"but got: {result!r}"
        )
