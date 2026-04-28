"""Tests for latency monitoring, failover transcription, and audit logging.

Validates that:
- Latency ≤ 3s continues using the primary (Whisper) transcriber
- Latency > 3s triggers automatic failover to Google STT v2
- Failover events are logged with correct details to the audit logger
- Failover is transparent — always returns a valid TranscriptionResult

Requirements: 1.5, 1.6
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from speech_ingestion.audit_logger import (
    AuditEntry,
    AuditLogger,
    BigQueryAuditLogger,
    MockAuditLogger,
)
from speech_ingestion.failover_transcriber import (
    DEFAULT_LATENCY_THRESHOLD_SECONDS,
    FailoverTranscriber,
    LatencyMeasurement,
)
from speech_ingestion.latency_monitor import LatencyMonitor, LatencyRecord
from speech_ingestion.transcriber import (
    MockWhisperTranscriber,
    Transcriber,
    TranscriptionResult,
)


# ---------------------------------------------------------------------------
# Helpers: mock transcribers that simulate different latencies
# ---------------------------------------------------------------------------


class SlowTranscriber:
    """Mock transcriber that sleeps to simulate high latency."""

    def __init__(self, delay_seconds: float, text: str = "[slow]", language: str = "hi") -> None:
        self._delay = delay_seconds
        self._text = text
        self._language = language
        self.call_count: int = 0

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        time.sleep(self._delay)
        self.call_count += 1
        return TranscriptionResult(text=self._text, language=self._language, confidence=0.85)


class FastTranscriber:
    """Mock transcriber that returns instantly (no artificial delay)."""

    def __init__(self, text: str = "[fast-primary]", language: str = "hi") -> None:
        self._text = text
        self._language = language
        self.call_count: int = 0

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        self.call_count += 1
        return TranscriptionResult(text=self._text, language=self._language, confidence=0.95)


class FallbackTranscriber:
    """Mock transcriber representing Google STT v2 fallback."""

    def __init__(self, text: str = "[google-stt-v2]", language: str = "hi") -> None:
        self._text = text
        self._language = language
        self.call_count: int = 0

    def transcribe(self, audio_chunk: bytes) -> TranscriptionResult:
        self.call_count += 1
        return TranscriptionResult(text=self._text, language=self._language, confidence=0.90)


SAMPLE_CHUNK = b"\x00" * 16000  # 500ms of silence at 16kHz/16-bit


# ===========================================================================
# AuditLogger tests
# ===========================================================================


class TestMockAuditLogger:
    """MockAuditLogger records entries in memory."""

    def test_satisfies_protocol(self):
        logger = MockAuditLogger()
        assert isinstance(logger, AuditLogger)

    def test_log_records_entry(self):
        logger = MockAuditLogger()
        entry = AuditEntry(
            call_id="call-1",
            event_type="failover",
            timestamp=datetime.now(timezone.utc),
            payload={"latency_seconds": 3.5},
        )
        logger.log(entry)
        assert len(logger.entries) == 1
        assert logger.last_entry() is entry

    def test_entries_for_call(self):
        logger = MockAuditLogger()
        e1 = AuditEntry(call_id="call-1", event_type="failover", timestamp=datetime.now(timezone.utc))
        e2 = AuditEntry(call_id="call-2", event_type="failover", timestamp=datetime.now(timezone.utc))
        e3 = AuditEntry(call_id="call-1", event_type="error", timestamp=datetime.now(timezone.utc))
        logger.log(e1)
        logger.log(e2)
        logger.log(e3)
        assert len(logger.entries_for("call-1")) == 2
        assert len(logger.entries_for("call-2")) == 1

    def test_last_entry_empty(self):
        logger = MockAuditLogger()
        assert logger.last_entry() is None


class TestBigQueryAuditLogger:
    """BigQueryAuditLogger placeholder raises NotImplementedError."""

    def test_satisfies_protocol(self):
        logger = BigQueryAuditLogger()
        assert isinstance(logger, AuditLogger)

    def test_raises_not_implemented(self):
        logger = BigQueryAuditLogger()
        entry = AuditEntry(call_id="call-1", event_type="failover", timestamp=datetime.now(timezone.utc))
        with pytest.raises(NotImplementedError, match="BigQueryAuditLogger"):
            logger.log(entry)


# ===========================================================================
# LatencyMonitor tests
# ===========================================================================


class TestLatencyMonitor:
    """LatencyMonitor wraps a transcriber and tracks latency."""

    def test_records_latency(self):
        monitor = LatencyMonitor(FastTranscriber())
        result, latency = monitor.transcribe(SAMPLE_CHUNK)
        assert isinstance(result, TranscriptionResult)
        assert latency >= 0.0
        assert len(monitor.records) == 1

    def test_exceeds_threshold_true(self):
        monitor = LatencyMonitor(FastTranscriber(), threshold_seconds=3.0)
        assert monitor.exceeds_threshold(3.1) is True

    def test_exceeds_threshold_false(self):
        monitor = LatencyMonitor(FastTranscriber(), threshold_seconds=3.0)
        assert monitor.exceeds_threshold(3.0) is False
        assert monitor.exceeds_threshold(2.5) is False

    def test_average_latency_empty(self):
        monitor = LatencyMonitor(FastTranscriber())
        assert monitor.average_latency() == 0.0

    def test_max_latency_empty(self):
        monitor = LatencyMonitor(FastTranscriber())
        assert monitor.max_latency() == 0.0

    def test_breach_count(self):
        monitor = LatencyMonitor(FastTranscriber(), threshold_seconds=3.0)
        # Fast transcriber should not breach
        monitor.transcribe(SAMPLE_CHUNK)
        monitor.transcribe(SAMPLE_CHUNK)
        assert monitor.breach_count() == 0

    def test_reset_clears_records(self):
        monitor = LatencyMonitor(FastTranscriber())
        monitor.transcribe(SAMPLE_CHUNK)
        assert len(monitor.records) == 1
        monitor.reset()
        assert len(monitor.records) == 0


# ===========================================================================
# FailoverTranscriber tests
# ===========================================================================


class TestFailoverTranscriberFastPrimary:
    """When primary latency ≤ 3s, continue using primary (Whisper)."""

    def test_uses_primary_when_fast(self):
        primary = FastTranscriber(text="[whisper]")
        fallback = FallbackTranscriber(text="[google-stt-v2]")
        ft = FailoverTranscriber(primary, fallback)

        result = ft.transcribe(SAMPLE_CHUNK)

        assert result.text == "[whisper]"
        assert ft.using_fallback is False
        assert primary.call_count == 1
        assert fallback.call_count == 0

    def test_no_failover_logged(self):
        primary = FastTranscriber()
        fallback = FallbackTranscriber()
        logger = MockAuditLogger()
        ft = FailoverTranscriber(primary, fallback, audit_logger=logger)

        ft.transcribe(SAMPLE_CHUNK)

        assert len(logger.entries) == 0

    def test_measurements_recorded(self):
        primary = FastTranscriber()
        fallback = FallbackTranscriber()
        ft = FailoverTranscriber(primary, fallback)

        ft.transcribe(SAMPLE_CHUNK)
        ft.transcribe(SAMPLE_CHUNK)

        assert len(ft.measurements) == 2
        for m in ft.measurements:
            assert m.used_fallback is False


class TestFailoverTranscriberSlowPrimary:
    """When primary latency > 3s, trigger fallback to Google STT v2."""

    def test_switches_to_fallback_on_slow_primary(self):
        # Use a very low threshold so we don't need real sleeps
        primary = SlowTranscriber(delay_seconds=0.05, text="[slow-whisper]")
        fallback = FallbackTranscriber(text="[google-stt-v2]")
        ft = FailoverTranscriber(primary, fallback, threshold_seconds=0.01)

        result = ft.transcribe(SAMPLE_CHUNK)

        # Should have switched to fallback and returned fallback result
        assert result.text == "[google-stt-v2]"
        assert ft.using_fallback is True

    def test_subsequent_chunks_use_fallback(self):
        primary = SlowTranscriber(delay_seconds=0.05)
        fallback = FallbackTranscriber(text="[google-stt-v2]")
        ft = FailoverTranscriber(primary, fallback, threshold_seconds=0.01)

        # First chunk triggers failover
        ft.transcribe(SAMPLE_CHUNK)
        assert ft.using_fallback is True

        # Second chunk goes directly to fallback (primary not called again)
        primary_calls_before = primary.call_count
        result2 = ft.transcribe(SAMPLE_CHUNK)
        assert result2.text == "[google-stt-v2]"
        assert primary.call_count == primary_calls_before  # no new primary calls

    def test_failover_event_logged(self):
        primary = SlowTranscriber(delay_seconds=0.05)
        fallback = FallbackTranscriber()
        logger = MockAuditLogger()
        ft = FailoverTranscriber(primary, fallback, audit_logger=logger, threshold_seconds=0.01)

        ft.transcribe(SAMPLE_CHUNK)

        assert len(logger.entries) == 1
        entry = logger.last_entry()
        assert entry is not None
        assert entry.event_type == "failover"
        assert entry.payload["reason"] == "primary_latency_exceeded"
        assert entry.payload["latency_seconds"] > 0.01
        assert entry.payload["threshold_seconds"] == 0.01
        assert entry.payload["primary"] == "whisper_large_v3"
        assert entry.payload["fallback"] == "google_stt_v2"
        assert isinstance(entry.timestamp, datetime)

    def test_failover_event_logged_with_call_id(self):
        primary = SlowTranscriber(delay_seconds=0.05)
        fallback = FallbackTranscriber()
        logger = MockAuditLogger()
        ft = FailoverTranscriber(primary, fallback, audit_logger=logger, threshold_seconds=0.01)

        ft.transcribe_for_call("call-42", SAMPLE_CHUNK)

        entry = logger.last_entry()
        assert entry is not None
        assert entry.call_id == "call-42"
        assert entry.event_type == "failover"

    def test_failover_returns_valid_transcription_result(self):
        primary = SlowTranscriber(delay_seconds=0.05)
        fallback = FallbackTranscriber(text="fallback text", language="ta")
        ft = FailoverTranscriber(primary, fallback, threshold_seconds=0.01)

        result = ft.transcribe(SAMPLE_CHUNK)

        # Failover is transparent — returns a valid TranscriptionResult
        assert isinstance(result, TranscriptionResult)
        assert result.text == "fallback text"
        assert result.language == "ta"
        assert 0.0 <= result.confidence <= 1.0


class TestFailoverTranscriberReset:
    """Reset returns the transcriber to using the primary."""

    def test_reset_clears_fallback_state(self):
        primary = SlowTranscriber(delay_seconds=0.05)
        fallback = FallbackTranscriber()
        ft = FailoverTranscriber(primary, fallback, threshold_seconds=0.01)

        ft.transcribe(SAMPLE_CHUNK)
        assert ft.using_fallback is True

        ft.reset()
        assert ft.using_fallback is False
        assert len(ft.measurements) == 0


class TestFailoverTranscriberThreshold:
    """Verify the default threshold is 3 seconds."""

    def test_default_threshold(self):
        primary = FastTranscriber()
        fallback = FallbackTranscriber()
        ft = FailoverTranscriber(primary, fallback)
        assert ft.threshold_seconds == 3.0
        assert DEFAULT_LATENCY_THRESHOLD_SECONDS == 3.0
