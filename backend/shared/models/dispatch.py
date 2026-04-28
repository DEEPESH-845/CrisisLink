"""Dispatch recommendation and card data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class DispatchRecommendation(BaseModel):
    """A single ranked dispatch recommendation for a response unit."""

    unit_id: str
    unit_type: str
    hospital_or_station: str
    eta_minutes: float = Field(..., description="Traffic-aware ETA in minutes")
    capability_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Capability match score (0.0 to 1.0)",
    )
    composite_score: float = Field(
        ...,
        description="Weighted score: (0.6 × ETA_normalized) + (0.4 × capability_match)",
    )
    distance_km: float = Field(..., description="Straight-line distance in km")


class DispatchCard(BaseModel):
    """Ranked list of dispatch recommendations for a call."""

    call_id: str
    recommendations: list[DispatchRecommendation] = Field(
        ..., description="Top 3 ranked units (or all if fewer than 3)"
    )
    generated_at: datetime = Field(..., description="ISO 8601 timestamp")
    classification_ref: str = Field(
        ..., description="Reference to the Emergency_Classification"
    )
