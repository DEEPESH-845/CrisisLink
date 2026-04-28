"""FastAPI application for the CrisisLink Speech Ingestion Service.

Endpoints
---------
POST /api/v1/calls/{call_id}/audio-stream
    Accept a binary audio chunk (500 ms, PCM 16-bit, 16 kHz) and queue it
    for transcription.  Returns 202 Accepted immediately.

GET  /api/v1/calls/{call_id}/transcript
    Return the current transcript state for a given call including call_id,
    transcript text, detected language, and number of chunks processed.

Both endpoints require a valid Bearer token in the Authorization header.

Requirements: 1.1, 1.2
"""

from fastapi import Depends, FastAPI, HTTPException, Request, status

from .auth import verify_bearer_token
from .schemas import AudioStreamAccepted, TranscriptResponse
from .service import SpeechIngestionStore

app = FastAPI(
    title="CrisisLink Speech Ingestion Service",
    version="0.1.0",
    description="Receives audio chunks from the Telephony Bridge and produces streaming transcripts.",
)

# Shared in-memory store — in production this would be backed by a message
# queue and Firebase RTDB writes.
store = SpeechIngestionStore()


@app.post(
    "/api/v1/calls/{call_id}/audio-stream",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AudioStreamAccepted,
    summary="Ingest an audio chunk for a call",
)
async def ingest_audio_stream(
    call_id: str,
    request: Request,
    _token: str = Depends(verify_bearer_token),
) -> AudioStreamAccepted:
    """Accept a raw binary audio chunk and queue it for processing.

    The body should contain raw PCM 16-bit, 16 kHz audio data representing
    a ~500 ms segment.
    """
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must contain audio data",
        )

    state = store.ingest_chunk(call_id, body)

    return AudioStreamAccepted(
        call_id=call_id,
        status="accepted",
        chunks_processed=state.chunks_processed,
    )


@app.get(
    "/api/v1/calls/{call_id}/transcript",
    response_model=TranscriptResponse,
    summary="Retrieve the current transcript for a call",
)
async def get_transcript(
    call_id: str,
    _token: str = Depends(verify_bearer_token),
) -> TranscriptResponse:
    """Return the accumulated transcript state for *call_id*."""
    state = store.get_state(call_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No transcript found for call_id '{call_id}'",
        )

    return TranscriptResponse(
        call_id=state.call_id,
        transcript=state.transcript,
        language_detected=state.language_detected,
        chunks_processed=state.chunks_processed,
    )
