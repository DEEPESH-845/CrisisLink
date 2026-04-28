"""Request and response schemas for the Dispatch Service API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from shared.models import (
    DispatchCard,
    DispatchRecommendation,
    EmergencyClassification,
    Location,
)


# ---------------------------------------------------------------------------
# Recommend endpoint
# ---------------------------------------------------------------------------


class RecommendRequest(BaseModel):
    """Body for POST /api/v1/calls/{call_id}/dispatch/recommend."""

    classification: EmergencyClassification
    caller_location: Location


class RecommendResponse(BaseModel):
    """Response for the recommend endpoint."""

    recommendations: list[DispatchRecommendation]
    dispatch_card: DispatchCard


# ---------------------------------------------------------------------------
# Confirm endpoint
# ---------------------------------------------------------------------------


class ConfirmRequest(BaseModel):
    """Body for POST /api/v1/calls/{call_id}/dispatch/confirm."""

    unit_id: str = Field(..., description="ID of the unit to dispatch")


class ConfirmResponse(BaseModel):
    """Response for the confirm endpoint."""

    status: str = Field(default="dispatched")
    unit_id: str
