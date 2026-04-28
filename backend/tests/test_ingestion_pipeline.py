"""Tests for the integrated speech ingestion pipeline (chunker → transcriber → writer).

Verifies that SpeechIngestionStore correctly wires the AudioChunker,
Transcriber, and TranscriptWriter together.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

from speech_ingestion.chunker import CHUNK_SIZE_BYTES
from speech_ingestion.firebase_writer import MockTranscriptWriter
from speech_ingestion.service import SpeechIngestionStore
from speech_ingestion.transcriber import MockWhisperTranscriber


def _make_chunk(size: int = CHUNK_SIZE_BYTES, fill: int = 0x00) -> bytes:
    """Create a PCM audio chunk of the given size."""
    return bytes([fill]) * size


class TestPipelineWithTranscriber:
    """Full pipeline: chunker → transcriber → writer."""

    def test_complete_chunk_triggers_transcription(self):
        transcriber = MockWhisperTranscriber(default_text="namaste")
        writer = MockTranscriptWriter()
        store = SpeechIngestionStore(transcriber=transcriber, writer=writer)

        state = store.ingest_chunk("CALL-1", _make_chunk())

        assert transcriber.call_count == 1
        assert state.transcript == "namaste"
        assert state.language_detected == "hi"

    def test_partial_chunk_does_not_trigger_transcription(self):
        transcriber = MockWhisperTranscriber()
        store = SpeechIngestionStore(transcriber=transcriber)

        # Send less than one full chunk
        store.ingest_chunk("CALL-1", _make_chunk(CHUNK_SIZE_BYTES // 2))
        assert transcriber.call_count == 0

    def test_two_halves_produce_one_transcription(self):
        transcriber = MockWhisperTranscriber(default_text="hello")
        store = SpeechIngestionStore(transcriber=transcriber)

        half = CHUNK_SIZE_BYTES // 2
        store.ingest_chunk("CALL-1", _make_chunk(half))
        state = store.ingest_chunk("CALL-1", _make_chunk(half))

        assert transcriber.call_count == 1
        assert state.transcript == "hello"

    def test_rolling_transcript_accumulates(self):
        transcriber = MockWhisperTranscriber(default_text="word")
        store = SpeechIngestionStore(transcriber=transcriber)

        store.ingest_chunk("CALL-1", _make_chunk())
        state = store.ingest_chunk("CALL-1", _make_chunk())

        assert state.transcript == "word word"
        assert transcriber.call_count == 2

    def test_language_detected_updated(self):
        transcriber = MockWhisperTranscriber(default_language="ta")
        store = SpeechIngestionStore(transcriber=transcriber)

        state = store.ingest_chunk("CALL-1", _make_chunk())
        assert state.language_detected == "ta"

    def test_multiple_calls_independent(self):
        transcriber = MockWhisperTranscriber(default_text="seg")
        store = SpeechIngestionStore(transcriber=transcriber)

        store.ingest_chunk("CALL-A", _make_chunk())
        store.ingest_chunk("CALL-B", _make_chunk())
        store.ingest_chunk("CALL-A", _make_chunk())

        state_a = store.get_state("CALL-A")
        state_b = store.get_state("CALL-B")
        assert state_a is not None
        assert state_b is not None
        assert state_a.transcript == "seg seg"
        assert state_b.transcript == "seg"


class TestPipelineFirebaseWrites:
    """Transcripts are written to Firebase RTDB via the writer."""

    def test_writer_called_on_complete_chunk(self):
        transcriber = MockWhisperTranscriber(default_text="text")
        writer = MockTranscriptWriter()
        store = SpeechIngestionStore(transcriber=transcriber, writer=writer)

        store.ingest_chunk("CALL-1", _make_chunk())

        assert len(writer.writes) == 1
        record = writer.last_write()
        assert record is not None
        assert record.call_id == "CALL-1"
        assert record.path == "/calls/CALL-1/transcript"
        assert record.transcript == "text"
        assert record.language_detected == "hi"
        assert record.chunks_processed == 1

    def test_writer_not_called_on_partial_chunk(self):
        transcriber = MockWhisperTranscriber()
        writer = MockTranscriptWriter()
        store = SpeechIngestionStore(transcriber=transcriber, writer=writer)

        store.ingest_chunk("CALL-1", _make_chunk(CHUNK_SIZE_BYTES // 2))
        assert len(writer.writes) == 0

    def test_writer_receives_rolling_transcript(self):
        transcriber = MockWhisperTranscriber(default_text="w")
        writer = MockTranscriptWriter()
        store = SpeechIngestionStore(transcriber=transcriber, writer=writer)

        store.ingest_chunk("CALL-1", _make_chunk())
        store.ingest_chunk("CALL-1", _make_chunk())

        assert len(writer.writes) == 2
        assert writer.writes[0].transcript == "w"
        assert writer.writes[1].transcript == "w w"

    def test_no_writer_still_works(self):
        """Pipeline works without a writer (in-memory only)."""
        transcriber = MockWhisperTranscriber(default_text="ok")
        store = SpeechIngestionStore(transcriber=transcriber, writer=None)

        state = store.ingest_chunk("CALL-1", _make_chunk())
        assert state.transcript == "ok"


class TestPipelineWithoutTranscriber:
    """Backwards compatibility: store works without a transcriber (task 3.1 mode)."""

    def test_chunks_counted_without_transcriber(self):
        store = SpeechIngestionStore()
        state = store.ingest_chunk("CALL-1", b"\x00" * 100)
        assert state.chunks_processed == 1
        assert state.transcript == ""
        assert state.language_detected == "unknown"

    def test_get_state_returns_none_for_unknown_call(self):
        store = SpeechIngestionStore()
        assert store.get_state("NONEXISTENT") is None

    def test_reset_clears_all(self):
        store = SpeechIngestionStore()
        store.ingest_chunk("CALL-1", b"\x00" * 100)
        store.reset()
        assert store.get_state("CALL-1") is None
