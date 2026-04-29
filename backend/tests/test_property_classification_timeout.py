"""Property-based test for classification timeout threshold.

Feature: crisislink-emergency-ai-copilot, Property 13: Classification Timeout Threshold

Validates: Requirements 11.4

Uses Hypothesis to generate random elapsed times (0.1–15.0s) and verify:
elapsed > 8s → timeout alert displayed; elapsed ≤ 8s → no timeout alert.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from intelligence.timeout_monitor import (
    CLASSIFICATION_TIMEOUT_SECONDS,
    ClassificationTimeoutMonitor,
    MockTimeoutAlertWriter,
    check_and_alert_timeout,
    configure_timeout,
    get_alert_writer,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Elapsed time values in the range [0.1, 15.0] as specified by the task
elapsed_strategy = st.floats(min_value=0.1, max_value=15.0, allow_nan=False)

# Elapsed times strictly above the 8s threshold
above_threshold_strategy = st.floats(
    min_value=8.0 + 1e-9, max_value=15.0, allow_nan=False
).filter(lambda x: x > CLASSIFICATION_TIMEOUT_SECONDS)

# Elapsed times at or below the 8s threshold
at_or_below_threshold_strategy = st.floats(
    min_value=0.1, max_value=8.0, allow_nan=False
)


# ---------------------------------------------------------------------------
# Property 13: Classification Timeout Threshold
# ---------------------------------------------------------------------------


class TestClassificationTimeoutThreshold:
    """Property 13: Classification Timeout Threshold

    For any call session, if the Intelligence Engine has not produced an
    Emergency_Classification within 8 seconds of the call connecting, the
    Operator Dashboard SHALL display a timeout alert and present the call
    for full manual handling. If classification arrives within 8 seconds,
    no timeout alert SHALL be triggered.

    **Validates: Requirements 11.4**
    """

    def setup_method(self):
        """Create a fresh monitor and mock writer for each test."""
        self.monitor = ClassificationTimeoutMonitor()
        self.writer = MockTimeoutAlertWriter()
        configure_timeout(monitor=self.monitor, alert_writer=self.writer)

    def teardown_method(self):
        """Reset module-level dependencies after each test."""
        configure_timeout(
            monitor=ClassificationTimeoutMonitor(),
            alert_writer=MockTimeoutAlertWriter(),
        )

    @given(elapsed=elapsed_strategy)
    @settings(max_examples=200)
    def test_timeout_decision_matches_threshold(self, elapsed: float):
        """For any elapsed time, timeout fires iff elapsed > 8s.

        **Validates: Requirements 11.4**
        """
        result = self.monitor.check_timeout(elapsed)

        if elapsed > CLASSIFICATION_TIMEOUT_SECONDS:
            assert result is True, (
                f"Expected timeout=True for elapsed={elapsed:.6f}s "
                f"> threshold={CLASSIFICATION_TIMEOUT_SECONDS}s"
            )
        else:
            assert result is False, (
                f"Expected timeout=False for elapsed={elapsed:.6f}s "
                f"<= threshold={CLASSIFICATION_TIMEOUT_SECONDS}s"
            )

    @given(elapsed=above_threshold_strategy)
    @settings(max_examples=200)
    def test_above_threshold_always_triggers_timeout(self, elapsed: float):
        """For any elapsed > 8s, a timeout alert is always triggered.

        **Validates: Requirements 11.4**
        """
        assert self.monitor.check_timeout(elapsed) is True, (
            f"Expected timeout=True for elapsed={elapsed:.6f}s "
            f"which exceeds threshold={CLASSIFICATION_TIMEOUT_SECONDS}s"
        )

    @given(elapsed=at_or_below_threshold_strategy)
    @settings(max_examples=200)
    def test_at_or_below_threshold_never_triggers_timeout(self, elapsed: float):
        """For any elapsed <= 8s, no timeout alert is triggered.

        **Validates: Requirements 11.4**
        """
        assert self.monitor.check_timeout(elapsed) is False, (
            f"Expected timeout=False for elapsed={elapsed:.6f}s "
            f"which is at or below threshold={CLASSIFICATION_TIMEOUT_SECONDS}s"
        )

    @given(elapsed=elapsed_strategy)
    @settings(max_examples=200)
    def test_check_and_alert_writes_alert_only_on_timeout(self, elapsed: float):
        """check_and_alert_timeout writes an alert iff elapsed > 8s.

        Verifies the full alert pipeline: the monitor detects the timeout
        and the alert writer records it for the Operator Dashboard.

        **Validates: Requirements 11.4**
        """
        writer = MockTimeoutAlertWriter()
        configure_timeout(
            monitor=ClassificationTimeoutMonitor(),
            alert_writer=writer,
        )

        call_id = "PROP-TEST-CALL"
        result = check_and_alert_timeout(call_id, elapsed)

        if elapsed > CLASSIFICATION_TIMEOUT_SECONDS:
            assert result is True, (
                f"Expected alert triggered for elapsed={elapsed:.6f}s"
            )
            assert len(writer.alerts) == 1, (
                f"Expected exactly 1 alert, got {len(writer.alerts)}"
            )
            alert = writer.alerts[0]
            assert alert["call_id"] == call_id
            assert alert["data"]["timeout"] is True
            assert alert["data"]["elapsed_seconds"] == elapsed
            assert alert["data"]["threshold_seconds"] == CLASSIFICATION_TIMEOUT_SECONDS
        else:
            assert result is False, (
                f"Expected no alert for elapsed={elapsed:.6f}s"
            )
            assert len(writer.alerts) == 0, (
                f"Expected 0 alerts, got {len(writer.alerts)}"
            )
