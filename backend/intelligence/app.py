"""FastAPI application for the CrisisLink Intelligence Service.

Endpoints
---------
POST /api/v1/calls/{call_id}/classify
    Accept a transcript string and return an Emergency_Classification.
    In production this will stream partial JSON via Gemini 1.5 Pro;
    the current implementation returns a stub classification.

POST /api/v1/calls/{call_id}/guidance
    Accept an Emergency_Classification and CallerState, and return
    guidance text for the caller.  Guidance is only generated when
    severity is CRITICAL or HIGH (Requirement 5.1).

Both endpoints require a valid Bearer token in the Authorization header.

Firebase RTDB Integration
-------------------------
The service sets up a listener on ``/calls/{call_id}/transcript`` for
rolling transcript consumption.  In this initial implementation the
listener infrastructure is provided but the real-time processing loop
will be wired in task 4.2 (Gemini integration).

Requirements: 2.1, 2.7, 5.1
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI

from .auth import verify_bearer_token
from .schemas import (
    ClassifyRequest,
    ClassifyResponse,
    GuidanceRequest,
    GuidanceResponse,
)
from .service import classify_transcript, generate_guidance

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CrisisLink Intelligence Service",
    version="0.1.0",
    description=(
        "Consumes rolling transcripts and produces emergency classifications "
        "and caller guidance via Gemini 1.5 Pro."
    ),
)

# ---------------------------------------------------------------------------
# Firebase RTDB transcript listener infrastructure
# ---------------------------------------------------------------------------

# In-memory registry of active transcript listeners keyed by call_id.
# Each entry stores the latest transcript snapshot received from RTDB.
_transcript_listeners: dict[str, dict[str, Any]] = {}


def _on_transcript_update(call_id: str, data: Any) -> None:
    """Callback invoked when ``/calls/{call_id}/transcript`` changes.

    Stores the latest transcript snapshot so the classify endpoint (or a
    background task in task 4.2) can consume it.
    """
    logger.info("Transcript update for call %s: %s", call_id, data)
    _transcript_listeners[call_id] = {"transcript": data}


def start_transcript_listener(call_id: str) -> None:
    """Register a Firebase RTDB listener for a call's transcript path.

    In production this will use ``firebase_admin.db.reference().listen()``.
    The stub initialises the in-memory entry so tests can verify the
    listener infrastructure without a live Firebase connection.
    """
    if call_id not in _transcript_listeners:
        _transcript_listeners[call_id] = {"transcript": ""}
        logger.info("Started transcript listener for call %s", call_id)


def get_transcript_snapshot(call_id: str) -> str | None:
    """Return the latest transcript snapshot for *call_id*, or ``None``."""
    entry = _transcript_listeners.get(call_id)
    if entry is None:
        return None
    return entry.get("transcript", "")


def reset_listeners() -> None:
    """Clear all transcript listeners (useful for testing)."""
    _transcript_listeners.clear()


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/calls/{call_id}/classify",
    response_model=ClassifyResponse,
    summary="Classify an emergency from a transcript",
)
async def classify(
    call_id: str,
    body: ClassifyRequest,
    _token: str = Depends(verify_bearer_token),
) -> ClassifyResponse:
    """Accept a transcript and return an Emergency_Classification.

    The endpoint also ensures a Firebase RTDB transcript listener is
    active for the given call so that subsequent transcript updates are
    consumed automatically.

    In the current stub implementation the classification is a default
    placeholder.  Task 4.2 will replace this with streamed Gemini output.
    """
    # Ensure a transcript listener is registered for this call
    start_transcript_listener(call_id)

    classification = classify_transcript(call_id, body.transcript)
    return ClassifyResponse(classification=classification)


@app.post(
    "/api/v1/calls/{call_id}/guidance",
    response_model=GuidanceResponse,
    summary="Generate caller guidance from classification and caller state",
)
async def guidance(
    call_id: str,
    body: GuidanceRequest,
    _token: str = Depends(verify_bearer_token),
) -> GuidanceResponse:
    """Accept an Emergency_Classification and CallerState, return guidance.

    Guidance is only generated when severity is CRITICAL or HIGH
    (Requirement 5.1).  For other severities the guidance field will be
    an empty string.

    Task 4.6 will replace the stub with Gemini-powered adaptive guidance.
    """
    guidance_text = generate_guidance(
        call_id=call_id,
        classification=body.classification,
        caller_state=body.caller_state,
    )
    return GuidanceResponse(call_id=call_id, guidance=guidance_text)
