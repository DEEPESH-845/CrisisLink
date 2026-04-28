"""Request/response schemas for the Speech Ingestion Service."""

from pydantic import BaseModel, Field


class TranscriptResponse(BaseModel):
    """Response schema for the transcript retrieval endpoint."""

    call_id: str = Field(..., description="Unique call session identifier")
    transcript: str = Field(
        default="", description="Rolling transcript text accumulated so far"
    )
    language_detected: str = Field(
        default="unknown",
        description="ISO 639-1 language code detected from audio",
    )
    chunks_processed: int = Field(
        default=0, description="Number of audio chunks processed for this call"
    )


class AudioStreamAccepted(BaseModel):
    """Response schema for the audio stream endpoint (202 Accepted)."""

    call_id: str
    status: str = "accepted"
    chunks_processed: int = Field(
        ..., description="Total chunks processed after this submission"
    )
