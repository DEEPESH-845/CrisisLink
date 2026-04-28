"""Call session data model."""

from datetime import datetime

from pydantic import BaseModel, Field

from .classification import CallerState, EmergencyClassification
from .dispatch import DispatchCard
from .enums import CallStatus, GuidanceStatus


class Guidance(BaseModel):
    """Guidance generation state for a call session."""

    status: GuidanceStatus
    language: str = Field(..., description="ISO 639-1 language code")
    protocol_type: str = Field(
        ..., description="Protocol identifier (e.g., CPR_IRC_2022, FIRE_NDMA)"
    )


class CallSession(BaseModel):
    """Full call session state stored in Firebase RTDB."""

    call_id: str
    status: CallStatus
    transcript: str = ""
    classification: EmergencyClassification | None = None
    caller_state: CallerState | None = None
    dispatch_card: DispatchCard | None = None
    confirmed_unit: str | None = Field(
        default=None, description="Dispatched unit_id"
    )
    guidance: Guidance | None = None
    manual_override: bool = False
    started_at: datetime = Field(..., description="ISO 8601 session start time")
    updated_at: datetime = Field(..., description="ISO 8601 last update time")
