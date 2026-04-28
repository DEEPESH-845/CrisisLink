"""Tests for the CrisisLink transcriber protocol and mock implementation.

Requirements: 1.1, 1.2, 1.3
"""

from speech_ingestion.transcriber import (
    MockWhisperTranscriber,
    Transcriber,
    TranscriptionResult,
    WhisperTranscriber,
    SCHEDULED_INDIAN_LANGUAGES,
)
import pytest


class TestTranscriptionResult:
    """TranscriptionResult data class tests."""

    def test_fields(self):
        result = TranscriptionResult(text="hello", language="en", confidence=0.9)
        assert result.text == "hello"
        assert result.language == "en"
        assert result.confidence == 0.9

    def test_default_confidence(self):
        result = TranscriptionResult(text="test", language="hi")
        assert result.confidence == 1.0


class TestMockWhisperTranscriber:
    """MockWhisperTranscriber returns deterministic results."""

    def test_satisfies_protocol(self):
        mock = MockWhisperTranscriber()
        assert isinstance(mock, Transcriber)

    def test_default_transcription(self):
        mock = MockWhisperTranscriber()
        result = mock.transcribe(b"\x00" * 16000)
        assert result.text == "[mock transcript]"
        assert result.language == "hi"
        assert result.confidence == 0.95

    def test_custom_defaults(self):
        mock = MockWhisperTranscriber(
            default_text="custom text",
            default_language="ta",
            default_confidence=0.8,
        )
        result = mock.transcribe(b"\x00" * 100)
        assert result.text == "custom text"
        assert result.language == "ta"
        assert result.confidence == 0.8

    def test_call_count_increments(self):
        mock = MockWhisperTranscriber()
        assert mock.call_count == 0
        mock.transcribe(b"\x00")
        mock.transcribe(b"\x00")
        assert mock.call_count == 2


class TestWhisperTranscriber:
    """WhisperTranscriber placeholder raises NotImplementedError."""

    def test_satisfies_protocol(self):
        wt = WhisperTranscriber()
        assert isinstance(wt, Transcriber)

    def test_raises_not_implemented(self):
        wt = WhisperTranscriber()
        with pytest.raises(NotImplementedError, match="GPU runtime"):
            wt.transcribe(b"\x00" * 16000)


class TestScheduledIndianLanguages:
    """Language map covers the 22 scheduled languages + English."""

    def test_contains_at_least_23_entries(self):
        assert len(SCHEDULED_INDIAN_LANGUAGES) >= 23

    def test_contains_hindi(self):
        assert "hi" in SCHEDULED_INDIAN_LANGUAGES

    def test_contains_tamil(self):
        assert "ta" in SCHEDULED_INDIAN_LANGUAGES

    def test_contains_english(self):
        assert "en" in SCHEDULED_INDIAN_LANGUAGES
