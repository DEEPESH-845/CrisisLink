"""Tests for classification timeout monitoring.

Verifies that the timeout monitor correctly identifies when classification
has exceeded the 8-second threshold (strictly greater than 8s triggers
timeout; at or below 8s does not).

Requirements: 11.4
"""

import pytest

from intelligence.timeout_monitor import (
    CLASSIFICATION_TIMEOUT_SECONDS,
    ClassificationTimeoutMonitor,
    MockTimeoutAlertWriter,
    check_and_alert_timeout,
    configure_timeout,
    get_alert_writer,
    write_timeout_alert,
)


class TestClassificationTimeoutMonitor:
    """Unit tests for the ClassificationTimeoutMonitor.check_timeout method."""

    def setup_method(self):
        self.monitor = ClassificationTimeoutMonitor()

    def test_elapsed_below_threshold_no_timeout(self):
        """Elapsed 7.9s → no timeout."""
        assert self.monitor.check_timeout(7.9) is False

    def test_elapsed_at_threshold_no_timeout(self):
        """Elapsed 8.0s → no timeout (at boundary, not exceeded)."""
        assert self.monitor.check_timeout(8.0) is False

    def test_elapsed_just_above_threshold_timeout(self):
        """Elapsed 8.1s → timeout."""
        assert self.monitor.check_timeout(8.1) is True

    def test_elapsed_well_above_threshold_timeout(self):
        """Elapsed 15.0s → timeout."""
        assert self.monitor.check_timeout(15.0) is True

    def test_elapsed_zero_no_timeout(self):
        """Elapsed 0.0s → no timeout."""
        assert self.monitor.check_timeout(0.0) is False

    def test_elapsed_exactly_at_boundary(self):
        """Elapsed exactly 8.0s → no timeout (strictly greater required)."""
        assert self.monitor.check_timeout(8.0) is False

    def test_threshold_constant_is_8(self):
        """Verify the timeout constant is 8.0 seconds."""
        assert CLASSIFICATION_TIMEOUT_SECONDS == 8.0

    def test_custom_timeout_threshold(self):
        """A custom timeout threshold should be respected."""
        custom = ClassificationTimeoutMonitor(timeout_seconds=5.0)
        assert custom.check_timeout(4.9) is False
        assert custom.check_timeout(5.0) is False
        assert custom.check_timeout(5.1) is True


class TestTimeoutAlertWrite:
    """Tests for timeout alert writing via the mock writer."""

    @pytest.fixture(autouse=True)
    def _setup_mock_writer(self):
        """Install a fresh mock alert writer before each test."""
        writer = MockTimeoutAlertWriter()
        configure_timeout(
            monitor=ClassificationTimeoutMonitor(),
            alert_writer=writer,
        )
        yield
        # Reset after test
        configure_timeout(
            monitor=ClassificationTimeoutMonitor(),
            alert_writer=MockTimeoutAlertWriter(),
        )

    def test_check_and_alert_triggers_on_timeout(self):
        """check_and_alert_timeout should write an alert when elapsed > 8s."""
        result = check_and_alert_timeout("CALL-TIMEOUT", 8.1)
        assert result is True
        writer = get_alert_writer()
        assert isinstance(writer, MockTimeoutAlertWriter)
        assert len(writer.alerts) == 1
        assert writer.alerts[0]["call_id"] == "CALL-TIMEOUT"

    def test_check_and_alert_no_trigger_within_threshold(self):
        """check_and_alert_timeout should NOT write an alert when elapsed <= 8s."""
        result = check_and_alert_timeout("CALL-OK", 7.5)
        assert result is False
        writer = get_alert_writer()
        assert isinstance(writer, MockTimeoutAlertWriter)
        assert len(writer.alerts) == 0

    def test_check_and_alert_no_trigger_at_boundary(self):
        """check_and_alert_timeout should NOT trigger at exactly 8.0s."""
        result = check_and_alert_timeout("CALL-BOUNDARY", 8.0)
        assert result is False
        writer = get_alert_writer()
        assert isinstance(writer, MockTimeoutAlertWriter)
        assert len(writer.alerts) == 0

    def test_timeout_alert_contains_elapsed_info(self):
        """The timeout alert data should include elapsed and threshold info."""
        check_and_alert_timeout("CALL-INFO", 10.5)
        writer = get_alert_writer()
        assert isinstance(writer, MockTimeoutAlertWriter)
        data = writer.alerts[0]["data"]
        assert data["timeout"] is True
        assert data["elapsed_seconds"] == 10.5
        assert data["threshold_seconds"] == 8.0

    def test_write_timeout_alert_directly(self):
        """write_timeout_alert should write an alert without checking elapsed."""
        write_timeout_alert("CALL-DIRECT")
        writer = get_alert_writer()
        assert isinstance(writer, MockTimeoutAlertWriter)
        assert len(writer.alerts) == 1
        assert writer.alerts[0]["call_id"] == "CALL-DIRECT"
        assert writer.alerts[0]["data"]["timeout"] is True
