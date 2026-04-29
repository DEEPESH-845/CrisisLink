"""Property-based test for speech failover threshold routing.

Feature: crisislink-emergency-ai-copilot, Property 4: Speech Failover Threshold Routing

Validates: Requirements 1.5

Uses Hypothesis to generate random latency values (0.1–10.0s) and verify
routing decision: latency > 3s → Google STT v2 fallback; latency ≤ 3s →
Whisper continues.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from speech_ingestion.failover_transcriber import (
    DEFAULT_LATENCY_THRESHOLD_SECONDS,
    FailoverTranscriber,
)
from speech_ingestion.latency_monitor import LatencyMonitor
from speech_ingestion.transcriber import TranscriptionResult


# ---------------------------------------------------------------------------
# Helpers: controllable-latency transcribers
# ---------------------------------------------------------------------------


class _ControlledLatencyTranscriber:
    """Transcriber whose latency is controlled via ``time.monotonic`` patching.

    The actual ``transcribe`` call returns instantly; the *simulated* latency
    is injected by advancing the monotonic clock in the test.
    """

    def __init__(self, text: str = "[primary]", language: str = "hi") -> None:
        self._text = text
        self._language = language
        self.call_count: int = 0

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        self.call_count += 1
        return TranscriptionResult(
            text=self._text, language=self._language, confidence=0.92
        )


class _FallbackTranscriber:
    """Simple fallback transcriber for Google STT v2."""

    def __init__(self, text: str = "[google-stt-v2]", language: str = "hi") -> None:
        self._text = text
        self._language = language
        self.call_count: int = 0

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        self.call_count += 1
        return TranscriptionResult(
            text=self._text, language=self._language, confidence=0.88
        )


SAMPLE_CHUNK = b"\x00" * 16000  # 500ms of silence at 16kHz/16-bit
THRESHOLD = DEFAULT_LATENCY_THRESHOLD_SECONDS  # 3.0s


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Latency values in the range [0.1, 10.0] as specified by the task
latency_strategy = st.floats(min_value=0.1, max_value=10.0, allow_nan=False)


# ---------------------------------------------------------------------------
# Property 4: Speech Failover Threshold Routing
# ---------------------------------------------------------------------------


class TestSpeechFailoverThresholdRouting:
    """Property 4: Speech Failover Threshold Routing

    For any Whisper transcription latency measurement, the Speech Ingestion
    Layer SHALL route audio to Google Speech-to-Text v2 fallback if and only
    if the measured latency exceeds 3 seconds per chunk. Latency values at or
    below 3 seconds SHALL continue using Whisper Large-v3.

    **Validates: Requirements 1.5**
    """

    @given(latency=latency_strategy)
    @settings(max_examples=200)
    def test_failover_routing_decision_matches_threshold(self, latency: float):
        """For any latency value, the routing decision is correct:
        latency > 3s → fallback (Google STT v2); latency ≤ 3s → primary (Whisper).

        **Validates: Requirements 1.5**
        """
        primary = _ControlledLatencyTranscriber(text="[whisper]")
        fallback = _FallbackTranscriber(text="[google-stt-v2]")
        ft = FailoverTranscriber(primary, fallback, threshold_seconds=THRESHOLD)

        # Simulate the desired latency by patching time.monotonic so that
        # the elapsed time inside FailoverTranscriber.transcribe equals
        # the generated latency value.
        call_count = 0
        base_time = 1000.0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            # First call is the "start" timestamp, second is the "end"
            if call_count % 2 == 1:
                return base_time
            return base_time + latency

        with patch("speech_ingestion.failover_transcriber.time.monotonic", side_effect=fake_monotonic):
            result = ft.transcribe(SAMPLE_CHUNK)

        if latency > THRESHOLD:
            # Should have failed over to Google STT v2
            assert ft.using_fallback is True, (
                f"Expected fallback for latency={latency:.4f}s > threshold={THRESHOLD}s"
            )
            assert result.text == "[google-stt-v2]", (
                f"Expected Google STT v2 result for latency={latency:.4f}s"
            )
            assert fallback.call_count >= 1, "Fallback transcriber should have been called"
        else:
            # Should continue using Whisper (primary)
            assert ft.using_fallback is False, (
                f"Expected primary for latency={latency:.4f}s <= threshold={THRESHOLD}s"
            )
            assert result.text == "[whisper]", (
                f"Expected Whisper result for latency={latency:.4f}s"
            )
            assert fallback.call_count == 0, "Fallback transcriber should NOT have been called"

    @given(latency=latency_strategy)
    @settings(max_examples=200)
    def test_latency_monitor_threshold_check_consistent(self, latency: float):
        """LatencyMonitor.exceeds_threshold agrees with the failover routing
        decision: exceeds_threshold(latency) ↔ latency > 3s.

        **Validates: Requirements 1.5**
        """
        primary = _ControlledLatencyTranscriber()
        monitor = LatencyMonitor(primary, threshold_seconds=THRESHOLD)

        exceeds = monitor.exceeds_threshold(latency)

        if latency > THRESHOLD:
            assert exceeds is True, (
                f"Expected exceeds_threshold=True for latency={latency:.4f}s > {THRESHOLD}s"
            )
        else:
            assert exceeds is False, (
                f"Expected exceeds_threshold=False for latency={latency:.4f}s <= {THRESHOLD}s"
            )

    @given(latency=latency_strategy)
    @settings(max_examples=200)
    def test_failover_records_measurement(self, latency: float):
        """Every transcription records a LatencyMeasurement with the correct
        used_fallback flag matching the routing decision.

        **Validates: Requirements 1.5**
        """
        primary = _ControlledLatencyTranscriber(text="[whisper]")
        fallback = _FallbackTranscriber(text="[google-stt-v2]")
        ft = FailoverTranscriber(primary, fallback, threshold_seconds=THRESHOLD)

        call_count = 0
        base_time = 1000.0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return base_time
            return base_time + latency

        with patch("speech_ingestion.failover_transcriber.time.monotonic", side_effect=fake_monotonic):
            ft.transcribe(SAMPLE_CHUNK)

        measurements = ft.measurements
        assert len(measurements) == 1, "Exactly one measurement should be recorded"

        m = measurements[0]
        expected_fallback = latency > THRESHOLD
        assert m.used_fallback is expected_fallback, (
            f"Measurement used_fallback={m.used_fallback} but expected "
            f"{expected_fallback} for latency={latency:.4f}s"
        )
