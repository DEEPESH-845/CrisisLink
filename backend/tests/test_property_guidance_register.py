"""Property-based test for guidance register selection.

Feature: crisislink-emergency-ai-copilot, Property 5: Guidance Register Selection

Validates: Requirements 3.4, 3.5, 3.6

Uses Hypothesis to generate all valid (panic_level, caller_role) enum pairs
and verify the correct guidance register is selected per the design mapping:
- PANIC_HIGH + VICTIM → REASSURANCE_FIRST (ultra-simple reassurance-first)
- PANIC_HIGH + BYSTANDER → DIRECTIVE_STEPS (directive numbered steps)
- CALM + BYSTANDER → CLINICAL_PROTOCOL (full clinical protocol)
- All other combinations → DEFAULT (defined default register)
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from intelligence.guidance_generator import (
    GuidanceRegister,
    select_guidance_register,
)
from shared.models import CallerRole, PanicLevel


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

panic_level_strategy = st.sampled_from(list(PanicLevel))
caller_role_strategy = st.sampled_from(list(CallerRole))


# ---------------------------------------------------------------------------
# Expected mapping (source of truth from design document)
# ---------------------------------------------------------------------------

_EXPECTED_REGISTER: dict[tuple[PanicLevel, CallerRole], GuidanceRegister] = {
    (PanicLevel.PANIC_HIGH, CallerRole.VICTIM): GuidanceRegister.REASSURANCE_FIRST,
    (PanicLevel.PANIC_HIGH, CallerRole.BYSTANDER): GuidanceRegister.DIRECTIVE_STEPS,
    (PanicLevel.CALM, CallerRole.BYSTANDER): GuidanceRegister.CLINICAL_PROTOCOL,
}


def _expected_register(panic_level: PanicLevel, caller_role: CallerRole) -> GuidanceRegister:
    """Return the expected guidance register for a given (panic_level, caller_role) pair."""
    return _EXPECTED_REGISTER.get((panic_level, caller_role), GuidanceRegister.DEFAULT)


# ---------------------------------------------------------------------------
# Property 5: Guidance Register Selection
# ---------------------------------------------------------------------------


class TestGuidanceRegisterSelection:
    """Property 5: Guidance Register Selection

    For any (panic_level, caller_role) pair from the Caller_State, the
    Guidance Generator SHALL select the correct guidance register:
    - PANIC_HIGH + VICTIM → ultra-simple reassurance-first (REASSURANCE_FIRST)
    - PANIC_HIGH + BYSTANDER → directive numbered steps (DIRECTIVE_STEPS)
    - CALM + BYSTANDER → full clinical protocol (CLINICAL_PROTOCOL)
    - All other valid combinations → defined default register (DEFAULT)

    **Validates: Requirements 3.4, 3.5, 3.6**
    """

    @given(panic_level=panic_level_strategy, caller_role=caller_role_strategy)
    @settings(max_examples=200)
    def test_register_matches_design_mapping(
        self,
        panic_level: PanicLevel,
        caller_role: CallerRole,
    ):
        """For any valid (panic_level, caller_role) pair, the selected register
        matches the design specification mapping.

        **Validates: Requirements 3.4, 3.5, 3.6**
        """
        result = select_guidance_register(panic_level, caller_role)
        expected = _expected_register(panic_level, caller_role)

        assert result == expected, (
            f"Expected register={expected.value} for "
            f"({panic_level.value}, {caller_role.value}), "
            f"got {result.value}"
        )

    @given(caller_role=caller_role_strategy)
    @settings(max_examples=200)
    def test_panic_high_victim_always_reassurance_first(
        self,
        caller_role: CallerRole,
    ):
        """PANIC_HIGH + VICTIM always selects REASSURANCE_FIRST regardless of
        other caller_role values generated (this test fixes VICTIM).

        **Validates: Requirements 3.4**
        """
        # This test specifically validates Requirement 3.4
        result = select_guidance_register(PanicLevel.PANIC_HIGH, CallerRole.VICTIM)
        assert result == GuidanceRegister.REASSURANCE_FIRST, (
            f"Expected REASSURANCE_FIRST for PANIC_HIGH + VICTIM, got {result.value}"
        )

    @given(panic_level=panic_level_strategy)
    @settings(max_examples=200)
    def test_panic_high_bystander_always_directive_steps(
        self,
        panic_level: PanicLevel,
    ):
        """PANIC_HIGH + BYSTANDER always selects DIRECTIVE_STEPS regardless of
        other panic_level values generated (this test fixes BYSTANDER).

        **Validates: Requirements 3.5**
        """
        # This test specifically validates Requirement 3.5
        result = select_guidance_register(PanicLevel.PANIC_HIGH, CallerRole.BYSTANDER)
        assert result == GuidanceRegister.DIRECTIVE_STEPS, (
            f"Expected DIRECTIVE_STEPS for PANIC_HIGH + BYSTANDER, got {result.value}"
        )

    @given(panic_level=panic_level_strategy)
    @settings(max_examples=200)
    def test_calm_bystander_always_clinical_protocol(
        self,
        panic_level: PanicLevel,
    ):
        """CALM + BYSTANDER always selects CLINICAL_PROTOCOL regardless of
        other panic_level values generated (this test fixes BYSTANDER).

        **Validates: Requirements 3.6**
        """
        # This test specifically validates Requirement 3.6
        result = select_guidance_register(PanicLevel.CALM, CallerRole.BYSTANDER)
        assert result == GuidanceRegister.CLINICAL_PROTOCOL, (
            f"Expected CLINICAL_PROTOCOL for CALM + BYSTANDER, got {result.value}"
        )

    @given(
        panic_level=st.sampled_from([PanicLevel.PANIC_MED, PanicLevel.INCOHERENT]),
        caller_role=caller_role_strategy,
    )
    @settings(max_examples=200)
    def test_non_special_panic_levels_always_default(
        self,
        panic_level: PanicLevel,
        caller_role: CallerRole,
    ):
        """For panic levels that are not PANIC_HIGH or CALM, and for CALM
        with non-BYSTANDER roles, the register is always DEFAULT.

        **Validates: Requirements 3.4, 3.5, 3.6**
        """
        result = select_guidance_register(panic_level, caller_role)
        assert result == GuidanceRegister.DEFAULT, (
            f"Expected DEFAULT for ({panic_level.value}, {caller_role.value}), "
            f"got {result.value}"
        )

    @given(caller_role=st.sampled_from([CallerRole.VICTIM, CallerRole.WITNESS]))
    @settings(max_examples=200)
    def test_calm_non_bystander_always_default(
        self,
        caller_role: CallerRole,
    ):
        """CALM + non-BYSTANDER roles always select DEFAULT.

        **Validates: Requirements 3.4, 3.5, 3.6**
        """
        result = select_guidance_register(PanicLevel.CALM, caller_role)
        assert result == GuidanceRegister.DEFAULT, (
            f"Expected DEFAULT for (CALM, {caller_role.value}), got {result.value}"
        )
