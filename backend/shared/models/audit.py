"""Audit log data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import AuditEventType


class AuditLogEntry(BaseModel):
    """Audit log entry written to BigQuery."""

    log_id: str = Field(..., description="Unique log entry ID")
    call_id: str
    event_type: AuditEventType
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )
    actor: str = Field(
        ..., description="System component or operator ID"
    )
    timestamp: datetime = Field(..., description="ISO 8601 timestamp")
