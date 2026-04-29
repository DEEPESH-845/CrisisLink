"""Property-based test for emergency protocol selection.

Feature: crisislink-emergency-ai-copilot, Property 9: Emergency Protocol Selection

Validates: Requirements 5.6, 5.7

Uses Hypothesis to generate random (emergency_type, key_facts) combinations
and verify the correct protocol is selected:
- MEDICAL + cardiac indicators in key_facts → CPR_IRC_2022
- FIRE → FIRE_NDMA
- All other emergency types → GENERAL

Cardiac indicators (matched case-insensitively): "cardiac", "heart attack",
"chest pain", "cardiac arrest", "cpr".
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from intelligence.guidance_generator import (
    CARDIAC_INDICATORS,
    GuidanceProtocol,
    select_guidance_protocol,
)
from shared.models import EmergencyType

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

emergency_type_strategy = st.sampled_from(list(EmergencyType))

# Non-MEDICAL, non-FIRE types that should always yield GENERAL
other_type_strategy = st.sampled_from([
    EmergencyType.CRIME,
    EmergencyType.ACCIDENT,
    EmergencyType.DISASTER,
    EmergencyType.UNKNOWN,
])

# Strategy for a single cardiac indicator keyword (possibly with varied case)
cardiac_indicator_strategy = st.sampled_from(sorted(CARDIAC_INDICATORS)).flatmap(
    lambda kw: st.sampled_from([kw, kw.upper(), kw.title()])
)

# Strategy for a key_facts list that contains at least one cardiac indicator
cardiac_key_facts_strategy = st.lists(
    st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
    min_size=0,
    max_size=5,
).flatmap(
    lambda base_facts: cardiac_indicator_strategy.map(
        lambda indicator: base_facts + [indicator]
    )
)

# Strategy for a key_facts list with NO cardiac indicators
_NON_CARDIAC_WORDS = [
    "broken leg", "bleeding", "fall", "unconscious person",
    "smoke inhalation", "burns", "fracture", "drowning",
    "seizure", "allergic reaction", "snake bite", "poisoning",
]

non_cardiac_key_facts_strategy = st.lists(
    st.sampled_from(_NON_CARDIAC_WORDS),
    min_size=0,
    max_size=5,
)

# General key_facts strategy (arbitrary text, no guarantee of cardiac keywords)
general_key_facts_strategy = st.lists(
    st.text(min_size=0, max_size=80, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
    min_size=0,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _facts_contain_cardiac_indicator(key_facts: list[str]) -> bool:
    """Return True if any fact contains a cardiac indicator (case-insensitive)."""
    for fact in key_facts:
        fact_lower = fact.lower()
        for indicator in CARDIAC_INDICATORS:
            if indicator in fact_lower:
                return True
    return False


# ---------------------------------------------------------------------------
# Property 9: Emergency Protocol Selection
# ---------------------------------------------------------------------------


class TestEmergencyProtocolSelection:
    """Property 9: Emergency Protocol Selection

    For any (emergency_type, key_facts) combination, the Guidance Generator
    SHALL select the correct protocol:
    - MEDICAL + cardiac indicators in key_facts → CPR_IRC_2022
    - FIRE → FIRE_NDMA
    - All other emergency types → GENERAL

    **Validates: Requirements 5.6, 5.7**
    """

    @given(
        emergency_type=emergency_type_strategy,
        key_facts=general_key_facts_strategy,
    )
    @settings(max_examples=200)
    def test_protocol_selection_matches_design_mapping(
        self,
        emergency_type: EmergencyType,
        key_facts: list[str],
    ) -> None:
        """For any valid (emergency_type, key_facts) pair, the selected
        protocol matches the design specification mapping.

        **Validates: Requirements 5.6, 5.7**
        """
        result = select_guidance_protocol(emergency_type, key_facts)

        if emergency_type == EmergencyType.MEDICAL and _facts_contain_cardiac_indicator(key_facts):
            expected = GuidanceProtocol.CPR_IRC_2022
        elif emergency_type == EmergencyType.FIRE:
            expected = GuidanceProtocol.FIRE_NDMA
        else:
            expected = GuidanceProtocol.GENERAL

        assert result == expected, (
            f"Expected protocol={expected.value} for "
            f"emergency_type={emergency_type.value}, "
            f"key_facts={key_facts!r}, got {result.value}"
        )

    @given(key_facts=cardiac_key_facts_strategy)
    @settings(max_examples=200)
    def test_medical_with_cardiac_indicators_returns_cpr_irc_2022(
        self,
        key_facts: list[str],
    ) -> None:
        """MEDICAL + key_facts containing cardiac indicators always selects
        CPR_IRC_2022.

        **Validates: Requirements 5.6**
        """
        result = select_guidance_protocol(EmergencyType.MEDICAL, key_facts)
        assert result == GuidanceProtocol.CPR_IRC_2022, (
            f"Expected CPR_IRC_2022 for MEDICAL with cardiac key_facts={key_facts!r}, "
            f"got {result.value}"
        )

    @given(key_facts=non_cardiac_key_facts_strategy)
    @settings(max_examples=200)
    def test_medical_without_cardiac_indicators_returns_general(
        self,
        key_facts: list[str],
    ) -> None:
        """MEDICAL + key_facts without cardiac indicators selects GENERAL.

        **Validates: Requirements 5.6**
        """
        result = select_guidance_protocol(EmergencyType.MEDICAL, key_facts)
        assert result == GuidanceProtocol.GENERAL, (
            f"Expected GENERAL for MEDICAL without cardiac key_facts={key_facts!r}, "
            f"got {result.value}"
        )

    @given(key_facts=general_key_facts_strategy)
    @settings(max_examples=200)
    def test_fire_always_returns_fire_ndma(
        self,
        key_facts: list[str],
    ) -> None:
        """FIRE emergency type always selects FIRE_NDMA regardless of key_facts.

        **Validates: Requirements 5.7**
        """
        result = select_guidance_protocol(EmergencyType.FIRE, key_facts)
        assert result == GuidanceProtocol.FIRE_NDMA, (
            f"Expected FIRE_NDMA for FIRE with key_facts={key_facts!r}, "
            f"got {result.value}"
        )

    @given(
        emergency_type=other_type_strategy,
        key_facts=general_key_facts_strategy,
    )
    @settings(max_examples=200)
    def test_other_types_always_return_general(
        self,
        emergency_type: EmergencyType,
        key_facts: list[str],
    ) -> None:
        """Emergency types other than MEDICAL and FIRE always select GENERAL
        regardless of key_facts content.

        **Validates: Requirements 5.6, 5.7**
        """
        result = select_guidance_protocol(emergency_type, key_facts)
        assert result == GuidanceProtocol.GENERAL, (
            f"Expected GENERAL for emergency_type={emergency_type.value} "
            f"with key_facts={key_facts!r}, got {result.value}"
        )

    @given(
        cardiac_indicator=cardiac_indicator_strategy,
        other_facts=non_cardiac_key_facts_strategy,
    )
    @settings(max_examples=200)
    def test_cardiac_indicator_case_insensitive_matching(
        self,
        cardiac_indicator: str,
        other_facts: list[str],
    ) -> None:
        """Cardiac indicators are matched case-insensitively. A fact containing
        any casing variant of a cardiac keyword triggers CPR_IRC_2022 for MEDICAL.

        **Validates: Requirements 5.6**
        """
        key_facts = other_facts + [cardiac_indicator]
        result = select_guidance_protocol(EmergencyType.MEDICAL, key_facts)
        assert result == GuidanceProtocol.CPR_IRC_2022, (
            f"Expected CPR_IRC_2022 for MEDICAL with cardiac indicator "
            f"'{cardiac_indicator}' in key_facts={key_facts!r}, got {result.value}"
        )
