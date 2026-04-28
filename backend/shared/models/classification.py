"""Emergency classification data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import CallerRole, EmergencyType, PanicLevel, Severity


class CallerState(BaseModel):
    """Caller emotional and cognitive state."""

    panic_level: PanicLevel
    caller_role: CallerRole


class EmergencyClassification(BaseModel):
    """Structured output from the Intelligence Engine for emergency triage."""

    call_id: str
    emergency_type: EmergencyType
    severity: Severity
    caller_state: CallerState
    language_detected: str = Field(
        ..., description="ISO 639-1 language code"
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description="Extracted facts (location clues, symptoms, numbers)",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence score"
    )
    timestamp: datetime = Field(
        ..., description="ISO 8601 timestamp of classification"
    )
    model_version: str = Field(
        ..., description="Gemini model version used for classification"
    )
