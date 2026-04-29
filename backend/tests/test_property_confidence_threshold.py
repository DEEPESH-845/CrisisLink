"""Property-based test for confidence threshold flagging.

Feature: crisislink-emergency-ai-copilot, Property 3: Confidence Threshold Flagging

Validates: Requirements 2.6, 6.6

Uses Hypothesis to generate random confidence floats in [0.0, 1.0] and verify:
confidence < 0.7 → flag for manual takeover; confidence ≥ 0.7 → no flag.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from intelligence.confidence_flagging import (
    CONFIDENCE_THRESHOLD,
    should_flag_for_manual_takeover,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Confidence values in the range [0.0, 1.0] as specified by the task
confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# ---------------------------------------------------------------------------
# Property 3: Confidence Threshold Flagging
# ---------------------------------------------------------------------------


class TestConfidenceThresholdFlagging:
    """Property 3: Confidence Threshold Flagging

    For any Emergency_Classification with a confidence score, the system SHALL
    flag the call for manual operator takeover if and only if the confidence
    score is strictly below 0.7. Classifications with confidence >= 0.7 SHALL
    NOT trigger the flag.

    **Validates: Requirements 2.6, 6.6**
    """

    @given(confidence=confidence_strategy)
    @settings(max_examples=200)
    def test_low_confidence_flags_for_manual_takeover(self, confidence: float):
        """For any confidence < 0.7, should_flag_for_manual_takeover returns True.

        **Validates: Requirements 2.6, 6.6**
        """
        result = should_flag_for_manual_takeover(confidence)

        if confidence < CONFIDENCE_THRESHOLD:
            assert result is True, (
                f"Expected flag=True for confidence={confidence:.6f} "
                f"< threshold={CONFIDENCE_THRESHOLD}"
            )
        else:
            assert result is False, (
                f"Expected flag=False for confidence={confidence:.6f} "
                f">= threshold={CONFIDENCE_THRESHOLD}"
            )

    @given(confidence=st.floats(min_value=0.0, max_value=0.6999999, allow_nan=False))
    @settings(max_examples=200)
    def test_below_threshold_always_flagged(self, confidence: float):
        """For any confidence strictly below 0.7, the call is always flagged.

        **Validates: Requirements 2.6, 6.6**
        """
        assert should_flag_for_manual_takeover(confidence) is True, (
            f"Expected flag=True for confidence={confidence:.6f} "
            f"which is below threshold={CONFIDENCE_THRESHOLD}"
        )

    @given(confidence=st.floats(min_value=0.7, max_value=1.0, allow_nan=False))
    @settings(max_examples=200)
    def test_at_or_above_threshold_never_flagged(self, confidence: float):
        """For any confidence >= 0.7, the call is never flagged.

        **Validates: Requirements 2.6, 6.6**
        """
        assert should_flag_for_manual_takeover(confidence) is False, (
            f"Expected flag=False for confidence={confidence:.6f} "
            f"which is at or above threshold={CONFIDENCE_THRESHOLD}"
        )
