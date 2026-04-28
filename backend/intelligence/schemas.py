"""Request/response schemas for the Intelligence Service.

These schemas define the API contract for the ``/classify`` and
``/guidance`` endpoints.  The shared Pydantic models from
``shared.models`` are used for the core domain types.
"""

from pydantic import BaseModel, Field

from shared.models import CallerState, EmergencyClassification


class ClassifyRequest(BaseModel):
    """Request body for ``POST /api/v1/calls/{call_id}/classify``."""

    transcript: str = Field(
        ..., description="Rolling transcript text to classify"
    )


class ClassifyResponse(BaseModel):
    """Response body for the classify endpoint.

    Wraps an ``EmergencyClassification`` so the endpoint can return
    additional metadata in the future without breaking the contract.
    """

    classification: EmergencyClassification


class GuidanceRequest(BaseModel):
    """Request body for ``POST /api/v1/calls/{call_id}/guidance``."""

    classification: EmergencyClassification = Field(
        ..., description="Emergency classification for the call"
    )
    caller_state: CallerState = Field(
        ..., description="Current caller emotional/cognitive state"
    )


class GuidanceResponse(BaseModel):
    """Response body for the guidance endpoint."""

    call_id: str = Field(..., description="Call session identifier")
    guidance: str = Field(
        ..., description="Generated guidance text for the caller"
    )
