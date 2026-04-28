"""Failover transcriber with latency-based routing for the Speech Ingestion Service.

Wraps a primary transcriber (Whisper Large-v3) and a fallback transcriber
(Google Speech-to-Text v2).  Measures the primary transcriber's latency per
chunk and automatically routes to the fallback when latency exceeds a
configurable threshold (default: 3 seconds).

Failover events are logged via an ``AuditLogger`` with timestamp, measured
latency, and failover reason.

Requirements: 1.5, 1.6
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .audit_logger import AuditEntry, AuditLogger
from .transcriber import Transcriber, TranscriptionResult


# Default latency threshold in seconds — matches design spec (3s per chunk).
DEFAULT_LATENCY_THRESHOLD_SECONDS: float = 3.0


@dataclass
class LatencyMeasurement:
    """Record of a single transcription latency measurement."""

    latency_seconds: float
    used_fallback: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FailoverTranscriber:
    """Transcriber that routes between primary and fallback based on latency.

    Measures the wall-clock time of the primary transcriber for each chunk.
    If the measured latency exceeds ``threshold_seconds``, the chunk is
    re-transcribed using the fallback transcriber and all subsequent chunks
    are routed to the fallback until :meth:`reset` is called.

    Parameters
    ----------
    primary : Transcriber
        The preferred transcriber (e.g. Whisper Large-v3).
    fallback : Transcriber
        The backup transcriber (e.g. Google STT v2).
    audit_logger : AuditLogger | None
        Optional logger for recording failover events.
    threshold_seconds : float
        Maximum acceptable latency for the primary transcriber.
    """

    def __init__(
        self,
        primary: Transcriber,
        fallback: Transcriber,
        audit_logger: AuditLogger | None = None,
        threshold_seconds: float = DEFAULT_LATENCY_THRESHOLD_SECONDS,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._audit_logger = audit_logger
        self._threshold = threshold_seconds
        self._using_fallback = False
        self._measurements: list[LatencyMeasurement] = []

    @property
    def using_fallback(self) -> bool:
        """Whether the transcriber has switched to the fallback."""
        return self._using_fallback

    @property
    def measurements(self) -> list[LatencyMeasurement]:
        """All latency measurements recorded so far."""
        return list(self._measurements)

    @property
    def threshold_seconds(self) -> float:
        """The latency threshold in seconds."""
        return self._threshold

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe *audio_chunk* using primary or fallback transcriber.

        If already in fallback mode, routes directly to the fallback.
        Otherwise, measures primary latency and switches to fallback if
        the threshold is exceeded.

        Returns a valid ``TranscriptionResult`` regardless of which
        transcriber is used — the failover is transparent to callers.
        """
        if self._using_fallback:
            result = self._fallback.transcribe(audio_chunk)
            self._measurements.append(
                LatencyMeasurement(latency_seconds=0.0, used_fallback=True)
            )
            return result

        # Measure primary transcription latency
        start = time.monotonic()
        result = self._primary.transcribe(audio_chunk)
        elapsed = time.monotonic() - start

        if elapsed > self._threshold:
            # Primary too slow — switch to fallback
            self._using_fallback = True
            self._measurements.append(
                LatencyMeasurement(latency_seconds=elapsed, used_fallback=True)
            )
            self._log_failover(
                call_id="",  # caller should set via transcribe_for_call
                latency=elapsed,
            )
            # Re-transcribe with fallback for this chunk
            result = self._fallback.transcribe(audio_chunk)
            return result

        # Primary was fast enough
        self._measurements.append(
            LatencyMeasurement(latency_seconds=elapsed, used_fallback=False)
        )
        return result

    def transcribe_for_call(self, call_id: str, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe with call_id context for audit logging.

        Same as :meth:`transcribe` but includes the *call_id* in any
        failover audit log entries.
        """
        if self._using_fallback:
            result = self._fallback.transcribe(audio_chunk)
            self._measurements.append(
                LatencyMeasurement(latency_seconds=0.0, used_fallback=True)
            )
            return result

        start = time.monotonic()
        result = self._primary.transcribe(audio_chunk)
        elapsed = time.monotonic() - start

        if elapsed > self._threshold:
            self._using_fallback = True
            self._measurements.append(
                LatencyMeasurement(latency_seconds=elapsed, used_fallback=True)
            )
            self._log_failover(call_id=call_id, latency=elapsed)
            result = self._fallback.transcribe(audio_chunk)
            return result

        self._measurements.append(
            LatencyMeasurement(latency_seconds=elapsed, used_fallback=False)
        )
        return result

    def reset(self) -> None:
        """Reset failover state — return to using the primary transcriber."""
        self._using_fallback = False
        self._measurements.clear()

    def _log_failover(self, call_id: str, latency: float) -> None:
        """Log a failover event via the audit logger."""
        if self._audit_logger is None:
            return

        entry = AuditEntry(
            call_id=call_id,
            event_type="failover",
            timestamp=datetime.now(timezone.utc),
            payload={
                "reason": "primary_latency_exceeded",
                "latency_seconds": round(latency, 4),
                "threshold_seconds": self._threshold,
                "primary": "whisper_large_v3",
                "fallback": "google_stt_v2",
            },
        )
        self._audit_logger.log(entry)
