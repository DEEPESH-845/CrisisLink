"""Tests for the CrisisLink audio chunker.

Covers:
- Correct segmentation of audio into 500ms (16 000 byte) chunks
- Partial chunk buffering until a complete chunk is available
- Empty audio handling
- Flush of remaining buffered audio
- Multiple sequential additions

Requirements: 1.1, 1.2
"""

import pytest

from speech_ingestion.chunker import CHUNK_SIZE_BYTES, AudioChunker


class TestAudioChunkerSegmentation:
    """Audio is correctly segmented into 500ms chunks."""

    def test_exact_single_chunk(self):
        """Feeding exactly one chunk's worth of data yields one chunk."""
        chunker = AudioChunker()
        audio = b"\x00" * CHUNK_SIZE_BYTES
        chunks = chunker.add_audio(audio)
        assert len(chunks) == 1
        assert len(chunks[0]) == CHUNK_SIZE_BYTES

    def test_exact_multiple_chunks(self):
        """Feeding exactly N chunks' worth of data yields N chunks."""
        chunker = AudioChunker()
        n = 5
        audio = b"\x00" * (CHUNK_SIZE_BYTES * n)
        chunks = chunker.add_audio(audio)
        assert len(chunks) == n
        for chunk in chunks:
            assert len(chunk) == CHUNK_SIZE_BYTES

    def test_chunk_content_preserved(self):
        """Chunk content matches the original audio bytes."""
        chunker = AudioChunker()
        # Two distinct chunks
        part_a = b"\xAA" * CHUNK_SIZE_BYTES
        part_b = b"\xBB" * CHUNK_SIZE_BYTES
        chunks = chunker.add_audio(part_a + part_b)
        assert chunks[0] == part_a
        assert chunks[1] == part_b

    def test_chunk_size_constant(self):
        """CHUNK_SIZE_BYTES equals 16 000 (500ms at 16 kHz, 16-bit mono)."""
        assert CHUNK_SIZE_BYTES == 16_000


class TestAudioChunkerBuffering:
    """Partial chunks are buffered until a complete chunk is available."""

    def test_partial_audio_buffered(self):
        """Audio smaller than one chunk is buffered, no chunks returned."""
        chunker = AudioChunker()
        partial = b"\x00" * (CHUNK_SIZE_BYTES - 1)
        chunks = chunker.add_audio(partial)
        assert chunks == []
        assert chunker.buffered_bytes == CHUNK_SIZE_BYTES - 1

    def test_partial_completes_on_next_add(self):
        """Buffered partial + new data yields a chunk when threshold is met."""
        chunker = AudioChunker()
        half = CHUNK_SIZE_BYTES // 2
        # First add: half a chunk — no output
        assert chunker.add_audio(b"\x00" * half) == []
        # Second add: the other half — one chunk
        chunks = chunker.add_audio(b"\x00" * half)
        assert len(chunks) == 1
        assert len(chunks[0]) == CHUNK_SIZE_BYTES

    def test_partial_plus_extra(self):
        """Buffered partial + more than enough data yields chunk + leftover."""
        chunker = AudioChunker()
        half = CHUNK_SIZE_BYTES // 2
        extra = 100
        chunker.add_audio(b"\x00" * half)
        chunks = chunker.add_audio(b"\x00" * (half + extra))
        assert len(chunks) == 1
        assert chunker.buffered_bytes == extra

    def test_incremental_small_additions(self):
        """Many small additions eventually produce a chunk."""
        chunker = AudioChunker()
        step = 1000  # 1 000 bytes at a time
        total_added = 0
        chunks_received: list[bytes] = []
        while total_added < CHUNK_SIZE_BYTES * 2:
            result = chunker.add_audio(b"\x00" * step)
            chunks_received.extend(result)
            total_added += step
        # Should have produced at least 2 chunks
        assert len(chunks_received) >= 2


class TestAudioChunkerEmptyHandling:
    """Empty audio input is handled gracefully."""

    def test_empty_bytes_returns_empty_list(self):
        chunker = AudioChunker()
        assert chunker.add_audio(b"") == []

    def test_empty_bytes_does_not_affect_buffer(self):
        chunker = AudioChunker()
        chunker.add_audio(b"\x00" * 100)
        assert chunker.buffered_bytes == 100
        chunker.add_audio(b"")
        assert chunker.buffered_bytes == 100


class TestAudioChunkerFlush:
    """Flush returns remaining buffered audio."""

    def test_flush_returns_partial(self):
        chunker = AudioChunker()
        chunker.add_audio(b"\xAB" * 500)
        flushed = chunker.flush()
        assert flushed is not None
        assert len(flushed) == 500
        assert chunker.buffered_bytes == 0

    def test_flush_empty_returns_none(self):
        chunker = AudioChunker()
        assert chunker.flush() is None

    def test_flush_after_exact_chunk_returns_none(self):
        chunker = AudioChunker()
        chunker.add_audio(b"\x00" * CHUNK_SIZE_BYTES)
        assert chunker.flush() is None


class TestAudioChunkerReset:
    """Reset clears all buffered audio."""

    def test_reset_clears_buffer(self):
        chunker = AudioChunker()
        chunker.add_audio(b"\x00" * 5000)
        chunker.reset()
        assert chunker.buffered_bytes == 0
