"""Tests for the CrisisLink Firebase transcript writer.

Requirements: 1.2, 1.4
"""

import pytest

from speech_ingestion.firebase_writer import (
    FirebaseTranscriptWriter,
    MockTranscriptWriter,
    TranscriptWriter,
)


class TestMockTranscriptWriter:
    """MockTranscriptWriter records writes for test assertions."""

    def test_satisfies_protocol(self):
        mock = MockTranscriptWriter()
        assert isinstance(mock, TranscriptWriter)

    def test_records_write(self):
        mock = MockTranscriptWriter()
        mock.write_transcript("CALL-1", "hello world", "hi", 1)
        assert len(mock.writes) == 1
        record = mock.writes[0]
        assert record.call_id == "CALL-1"
        assert record.transcript == "hello world"
        assert record.language_detected == "hi"
        assert record.chunks_processed == 1

    def test_path_uses_firebase_helper(self):
        mock = MockTranscriptWriter()
        mock.write_transcript("CALL-42", "text", "en", 3)
        assert mock.writes[0].path == "/calls/CALL-42/transcript"

    def test_last_write(self):
        mock = MockTranscriptWriter()
        assert mock.last_write() is None
        mock.write_transcript("C1", "a", "hi", 1)
        mock.write_transcript("C1", "a b", "hi", 2)
        assert mock.last_write() is not None
        assert mock.last_write().chunks_processed == 2

    def test_writes_for_filters_by_call_id(self):
        mock = MockTranscriptWriter()
        mock.write_transcript("C1", "a", "hi", 1)
        mock.write_transcript("C2", "b", "en", 1)
        mock.write_transcript("C1", "a c", "hi", 2)
        assert len(mock.writes_for("C1")) == 2
        assert len(mock.writes_for("C2")) == 1
        assert len(mock.writes_for("C3")) == 0


class TestFirebaseTranscriptWriter:
    """FirebaseTranscriptWriter placeholder raises NotImplementedError."""

    def test_satisfies_protocol(self):
        writer = FirebaseTranscriptWriter()
        assert isinstance(writer, TranscriptWriter)

    def test_raises_not_implemented(self):
        writer = FirebaseTranscriptWriter()
        with pytest.raises(NotImplementedError, match="firebase-admin"):
            writer.write_transcript("CALL-1", "text", "hi", 1)
