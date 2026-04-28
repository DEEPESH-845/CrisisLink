"""Response unit data models."""

from pydantic import BaseModel, Field

from .enums import UnitStatus, UnitType


class Location(BaseModel):
    """GPS coordinates."""

    lat: float
    lng: float


class ResponseUnit(BaseModel):
    """An emergency response vehicle tracked in Firebase RTDB."""

    unit_id: str = Field(..., description="Unique unit identifier (e.g., AMB_007)")
    type: UnitType
    status: UnitStatus
    location: Location
    hospital_or_station: str = Field(
        ..., description="Affiliated facility name"
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Capability tags (e.g., cardiac, trauma, pediatric, hazmat)",
    )
    last_updated: int = Field(
        ..., description="Unix timestamp of last location/status update"
    )
