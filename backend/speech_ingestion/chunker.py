"""Audio chunker for the CrisisLink Speech Ingestion Service.

Segments incoming raw PCM audio into fixed-size 500ms chunks suitable for
streaming transcription.  Audio format: PCM 16-bit signed, 16 kHz mono.

    500ms chunk = 16000 samples/sec × 0.5s × 2 bytes/sample = 16000 bytes

Requirements: 1.1, 1.2
"""

from __future__ import annotations

from dataclasses import dataclass, field

# PCM 16-bit, 16 kHz mono → 16000 samples/sec × 2 bytes = 32000 bytes/sec
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes per sample
CHANNELS = 1
CHUNK_DURATION_MS = 500

# Bytes per 500ms chunk: 16000 × 0.5 × 2 = 16000
CHUNK_SIZE_BYTES = int(SAMPLE_RATE * (CHUNK_DURATION_MS / 1000) * SAMPLE_WIDTH * CHANNELS)


@dataclass
class AudioChunker:
    """Buffers incoming PCM audio and yields complete 500ms chunks.

    Any leftover bytes that don't fill a complete chunk are retained in
    an internal buffer until the next call to :meth:`add_audio`.

    Parameters
    ----------
    chunk_size : int
        Size of each output chunk in bytes.  Defaults to
        :data:`CHUNK_SIZE_BYTES` (16 000 bytes for 500ms at 16 kHz/16-bit).
    """

    chunk_size: int = CHUNK_SIZE_BYTES
    _buffer: bytearray = field(default_factory=bytearray, repr=False)

    def add_audio(self, audio_data: bytes) -> list[bytes]:
        """Append *audio_data* to the internal buffer and return complete chunks.

        Returns a (possibly empty) list of ``bytes`` objects, each exactly
        ``chunk_size`` bytes long.  Any remainder stays buffered.
        """
        if not audio_data:
            return []

        self._buffer.extend(audio_data)

        chunks: list[bytes] = []
        while len(self._buffer) >= self.chunk_size:
            chunk = bytes(self._buffer[: self.chunk_size])
            del self._buffer[: self.chunk_size]
            chunks.append(chunk)

        return chunks

    @property
    def buffered_bytes(self) -> int:
        """Number of bytes currently waiting in the internal buffer."""
        return len(self._buffer)

    def flush(self) -> bytes | None:
        """Return any remaining buffered audio and clear the buffer.

        Returns ``None`` if the buffer is empty, otherwise returns the
        partial chunk as ``bytes``.
        """
        if not self._buffer:
            return None
        data = bytes(self._buffer)
        self._buffer.clear()
        return data

    def reset(self) -> None:
        """Discard all buffered audio."""
        self._buffer.clear()
