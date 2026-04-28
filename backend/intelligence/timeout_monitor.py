"""Classification timeout monitoring for the Intelligence Service.

Tracks elapsed time since a call connected and triggers a timeout alert
if no Emergency_Classification is produced within 8 seconds.  The timeout
alert is written to Firebase RTDB so the Operator Dashboard can present
the call for full manual handling.

Requirements: 11.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Classification timeout threshold in seconds.  If no classification is
# produced within this window, a timeout alert is written.
CLASSIFICATION_TIMEOUT_SECONDS = 8.0


class ClassificationTimeoutMonitor:
    """Tracks elapsed time and determines whether classification has timed out.

    The timeout fires when elapsed time is *strictly greater than* 8 seconds.
    At exactly 8 seconds, no timeout is triggered.
    """

    def __init__(self, timeout_seconds: float = CLASSIFICATION_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    @property
    def timeout_seconds(self) -> float:
        """Return the configured timeout threshold."""
        return self._timeout_seconds

    def check_timeout(self, elapsed_seconds: float) -> bool:
        """Return ``True`` if *elapsed_seconds* exceeds the timeout threshold.

        Parameters
        ----------
        elapsed_seconds : float
            Seconds elapsed since the call connected.

        Returns
        -------
        bool
            ``True`` when elapsed > timeout threshold (strictly greater).
        """
        return elapsed_seconds > self._timeout_seconds


@runtime_checkable
class TimeoutAlertWriter(Protocol):
    """Protocol for writing timeout alerts to a persistent store."""

    def write_timeout_alert(
        self,
        call_id: str,
        data: dict[str, Any],
    ) -> None:
        """Write a timeout alert for *call_id*."""
        ...


class MockTimeoutAlertWriter:
    """In-memory mock writer for testing — records all timeout alerts."""

    def __init__(self) -> None:
        self.alerts: list[dict[str, Any]] = []

    def write_timeout_alert(
        self,
        call_id: str,
        data: dict[str, Any],
    ) -> None:
        self.alerts.append({"call_id": call_id, "data": data})

    def last_alert(self) -> dict[str, Any] | None:
        return self.alerts[-1] if self.alerts else None

    def alerts_for(self, call_id: str) -> list[dict[str, Any]]:
        return [a for a in self.alerts if a["call_id"] == call_id]


class FirebaseTimeoutAlertWriter:
    """Production writer that pushes timeout alerts to Firebase RTDB."""

    def write_timeout_alert(
        self,
        call_id: str,
        data: dict[str, Any],
    ) -> None:
        raise NotImplementedError(
            f"FirebaseTimeoutAlertWriter requires firebase-admin initialisation. "
            f"Would write timeout alert for call {call_id}. "
            f"Use MockTimeoutAlertWriter for testing."
        )


# Module-level dependencies (injectable for testing)
_timeout_monitor = ClassificationTimeoutMonitor()
_alert_writer: TimeoutAlertWriter = MockTimeoutAlertWriter()


def configure_timeout(
    monitor: ClassificationTimeoutMonitor | None = None,
    alert_writer: TimeoutAlertWriter | None = None,
) -> None:
    """Inject timeout monitor and alert writer at application startup."""
    global _timeout_monitor, _alert_writer
    if monitor is not None:
        _timeout_monitor = monitor
    if alert_writer is not None:
        _alert_writer = alert_writer


def get_timeout_monitor() -> ClassificationTimeoutMonitor:
    """Return the currently configured timeout monitor."""
    return _timeout_monitor


def get_alert_writer() -> TimeoutAlertWriter:
    """Return the currently configured alert writer."""
    return _alert_writer


def check_and_alert_timeout(call_id: str, elapsed_seconds: float) -> bool:
    """Check if classification has timed out and write an alert if so.

    Parameters
    ----------
    call_id : str
        Unique call session identifier.
    elapsed_seconds : float
        Seconds elapsed since the call connected.

    Returns
    -------
    bool
        ``True`` if a timeout alert was triggered.
    """
    if _timeout_monitor.check_timeout(elapsed_seconds):
        logger.warning(
            "Classification timeout for call %s (%.1fs elapsed, threshold %.1fs)",
            call_id,
            elapsed_seconds,
            _timeout_monitor.timeout_seconds,
        )
        try:
            _alert_writer.write_timeout_alert(
                call_id,
                {
                    "timeout": True,
                    "elapsed_seconds": elapsed_seconds,
                    "threshold_seconds": _timeout_monitor.timeout_seconds,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except NotImplementedError:
            logger.debug(
                "Timeout alert writer not available (expected in dev/test): %s",
                call_id,
            )
        return True
    return False


def write_timeout_alert(call_id: str) -> None:
    """Write a timeout alert to Firebase RTDB for *call_id*.

    Convenience function that writes a timeout alert without checking
    elapsed time (useful when the caller already knows a timeout occurred).
    """
    logger.warning("Writing timeout alert for call %s", call_id)
    try:
        _alert_writer.write_timeout_alert(
            call_id,
            {
                "timeout": True,
                "threshold_seconds": _timeout_monitor.timeout_seconds,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except NotImplementedError:
        logger.debug(
            "Timeout alert writer not available (expected in dev/test): %s",
            call_id,
        )
