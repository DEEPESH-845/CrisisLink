"""CrisisLink enum definitions for all data models."""

from enum import Enum


class EmergencyType(str, Enum):
    """Emergency classification type."""

    MEDICAL = "MEDICAL"
    FIRE = "FIRE"
    CRIME = "CRIME"
    ACCIDENT = "ACCIDENT"
    DISASTER = "DISASTER"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    """Emergency severity level."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class PanicLevel(str, Enum):
    """Caller panic level classification."""

    PANIC_HIGH = "PANIC_HIGH"
    PANIC_MED = "PANIC_MED"
    CALM = "CALM"
    INCOHERENT = "INCOHERENT"


class CallerRole(str, Enum):
    """Caller role classification."""

    VICTIM = "VICTIM"
    BYSTANDER = "BYSTANDER"
    WITNESS = "WITNESS"


class UnitType(str, Enum):
    """Response unit type."""

    AMBULANCE = "ambulance"
    FIRE_BRIGADE = "fire_brigade"
    POLICE = "police"


class UnitStatus(str, Enum):
    """Response unit operational status."""

    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    ON_SCENE = "on_scene"
    RETURNING = "returning"


class CallStatus(str, Enum):
    """Call session status."""

    ACTIVE = "active"
    DISPATCHED = "dispatched"
    RESOLVED = "resolved"
    MANUAL_OVERRIDE = "manual_override"


class GuidanceStatus(str, Enum):
    """Guidance generation status."""

    GENERATING = "generating"
    ACTIVE = "active"
    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"


class AuditEventType(str, Enum):
    """Audit log event type."""

    CLASSIFICATION = "classification"
    OPERATOR_OVERRIDE = "operator_override"
    DISPATCH = "dispatch"
    FAILOVER = "failover"
    ERROR = "error"
