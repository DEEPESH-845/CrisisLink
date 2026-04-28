"""Latency monitor for tracking Whisper transcription time per chunk.

Provides a ``LatencyMonitor`` that wraps a ``Transcriber`` and records
wall-clock transcription time for each chunk.  This is used by the
``FailoverTranscriber`` and can also be used independently for metrics
and Cloud Monitoring integration.

Requirements: 1.5
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean

from .transcriber import Transcriber, TranscriptionResult


@dataclass
class LatencyRecord:
    """A single latency measurement for one transcription call."""

    latency_seconds: float
    chunk_size_bytes: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LatencyMonitor:
    """Wraps a ``Transcriber`` and measures transcription latency per chunk.

    Records every measurement for later analysis and exposes summary
    statistics (average, max, count of threshold breaches).

    Parameters
    ----------
    transcriber : Transcriber
        The transcriber to monitor.
    threshold_seconds : float
        Latency threshold for flagging slow transcriptions (default 3.0s).
    """

    def __init__(
        self,
        transcriber: Transcriber,
        threshold_seconds: float = 3.0,
    ) -> None:
        self._transcriber = transcriber
        self._threshold = threshold_seconds
        self._records: list[LatencyRecord] = []

    @property
    def records(self) -> list[LatencyRecord]:
        """All latency records collected so far."""
        return list(self._records)

    @property
    def threshold_seconds(self) -> float:
        """The configured latency threshold."""
        return self._threshold

    def transcribe(self, audio_chunk: bytes) -> tuple[TranscriptionResult, float]:
        """Transcribe *audio_chunk* and return the result with measured latency.

        Returns
        -------
        tuple[TranscriptionResult, float]
            The transcription result and the wall-clock latency in seconds.
        """
        start = time.monotonic()
        result = self._transcriber.transcribe(audio_chunk)
        elapsed = time.monotonic() - start

        self._records.append(
            LatencyRecord(
                latency_seconds=elapsed,
                chunk_size_bytes=len(audio_chunk),
            )
        )
        return result, elapsed

    def exceeds_threshold(self, latency: float) -> bool:
        """Return ``True`` if *latency* exceeds the configured threshold."""
        return latency > self._threshold

    def average_latency(self) -> float:
        """Return the average latency across all recorded measurements.

        Returns 0.0 if no measurements have been recorded.
        """
        if not self._records:
            return 0.0
        return mean(r.latency_seconds for r in self._records)

    def max_latency(self) -> float:
        """Return the maximum recorded latency, or 0.0 if none."""
        if not self._records:
            return 0.0
        return max(r.latency_seconds for r in self._records)

    def breach_count(self) -> int:
        """Return the number of measurements that exceeded the threshold."""
        return sum(1 for r in self._records if r.latency_seconds > self._threshold)

    def reset(self) -> None:
        """Clear all recorded measurements."""
        self._records.clear()
