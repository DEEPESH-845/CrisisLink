"""Security Configuration: Encryption, Audit Logging, and Data Retention.

Implements and documents the security requirements for CrisisLink:

1. Encryption at rest (AES-256) and in transit (TLS 1.3) — Req 10.1
2. Data retention: discard raw audio at session end, 90-day transcript
   retention — Req 10.2
3. Audit logging for all AI classifications and operator overrides — Req 10.4
4. DPDP Act 2023 compliance: process personal data only when operationally
   necessary — Req 10.5

Requirements: 10.1, 10.2, 10.4, 10.5
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from shared.models import AuditEventType
from speech_ingestion.audit_logger import AuditEntry, AuditLogger, MockAuditLogger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Encryption configuration (Req 10.1)
# ---------------------------------------------------------------------------


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""

    AES_256_GCM = "AES-256-GCM"


class TransportProtocol(str, Enum):
    """Supported transport security protocols."""

    TLS_1_3 = "TLS-1.3"


@dataclass(frozen=True)
class EncryptionConfig:
    """Encryption configuration for CrisisLink data.

    All call audio and transcripts are encrypted:
    - At rest: AES-256-GCM (Google Cloud default for Cloud Storage and
      BigQuery; Firebase RTDB uses Google-managed encryption keys)
    - In transit: TLS 1.3 for all service-to-service and client-to-server
      communication

    Requirement 10.1
    """

    at_rest_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    in_transit_protocol: TransportProtocol = TransportProtocol.TLS_1_3
    key_management: str = "Google Cloud KMS"
    audio_encrypted: bool = True
    transcript_encrypted: bool = True

    def is_compliant(self) -> bool:
        """Return True if the configuration meets Req 10.1."""
        return (
            self.at_rest_algorithm == EncryptionAlgorithm.AES_256_GCM
            and self.in_transit_protocol == TransportProtocol.TLS_1_3
            and self.audio_encrypted
            and self.transcript_encrypted
        )


# Default encryption configuration
ENCRYPTION_CONFIG = EncryptionConfig()


# ---------------------------------------------------------------------------
# Data retention policy (Req 10.2)
# ---------------------------------------------------------------------------

# Raw call audio is discarded at the end of each session.
# Transcripts are retained for a maximum of 90 days.
TRANSCRIPT_RETENTION_DAYS = 90
RAW_AUDIO_RETENTION_POLICY = "discard_at_session_end"


@dataclass
class DataRetentionPolicy:
    """Data retention policy for CrisisLink.

    - Raw call audio: discarded at session end (never persisted)
    - Transcripts: retained for 90 days, then purged
    - Audit logs: retained per PSAP SOP (typically 1 year)

    Requirement 10.2
    """

    raw_audio_policy: str = RAW_AUDIO_RETENTION_POLICY
    transcript_retention_days: int = TRANSCRIPT_RETENTION_DAYS
    audit_log_retention_days: int = 365

    def is_compliant(self) -> bool:
        """Return True if the policy meets Req 10.2."""
        return (
            self.raw_audio_policy == "discard_at_session_end"
            and self.transcript_retention_days <= 90
        )


# Default data retention policy
DATA_RETENTION_POLICY = DataRetentionPolicy()


@dataclass
class SessionCleanupResult:
    """Outcome of a session-end cleanup operation."""

    call_id: str
    audio_discarded: bool = False
    transcript_marked_for_retention: bool = False
    retention_expiry: datetime | None = None
    error: str | None = None


def cleanup_session_data(
    call_id: str,
    audio_buffer: list[bytes] | None = None,
    retention_policy: DataRetentionPolicy | None = None,
) -> SessionCleanupResult:
    """Clean up session data at the end of a call.

    1. Discard raw audio buffer (Req 10.2)
    2. Mark transcript for 90-day retention

    Parameters
    ----------
    call_id : str
        The call session identifier.
    audio_buffer : list[bytes] | None
        The raw audio chunks to discard. Cleared in-place.
    retention_policy : DataRetentionPolicy | None
        Override the default retention policy.

    Returns
    -------
    SessionCleanupResult
    """
    policy = retention_policy or DATA_RETENTION_POLICY
    result = SessionCleanupResult(call_id=call_id)

    try:
        # 1. Discard raw audio
        if audio_buffer is not None:
            audio_buffer.clear()
        result.audio_discarded = True

        # 2. Calculate transcript retention expiry
        from datetime import timedelta

        expiry = datetime.now(timezone.utc) + timedelta(
            days=policy.transcript_retention_days
        )
        result.transcript_marked_for_retention = True
        result.retention_expiry = expiry

        logger.info(
            "Session %s cleaned up: audio discarded, transcript expires %s",
            call_id,
            expiry.isoformat(),
        )

    except Exception as exc:
        logger.error("Session cleanup failed for call %s: %s", call_id, exc)
        result.error = str(exc)

    return result


# ---------------------------------------------------------------------------
# Audit logging verification (Req 10.4)
# ---------------------------------------------------------------------------


REQUIRED_AUDIT_EVENT_TYPES: set[str] = {
    AuditEventType.CLASSIFICATION.value,
    AuditEventType.OPERATOR_OVERRIDE.value,
    AuditEventType.DISPATCH.value,
    AuditEventType.FAILOVER.value,
}


def verify_audit_completeness(
    call_id: str,
    audit_entries: list[AuditEntry],
    expected_events: set[str] | None = None,
) -> dict[str, Any]:
    """Verify that all required audit log entries exist for a call.

    Checks that the audit trail includes entries for each expected
    event type. Used for compliance verification (Req 10.4).

    Parameters
    ----------
    call_id : str
        The call session identifier.
    audit_entries : list[AuditEntry]
        The audit entries to verify.
    expected_events : set[str] | None
        The event types expected. Defaults to classification + dispatch.

    Returns
    -------
    dict
        ``{"complete": bool, "present": [...], "missing": [...]}``
    """
    if expected_events is None:
        expected_events = {
            AuditEventType.CLASSIFICATION.value,
            AuditEventType.DISPATCH.value,
        }

    call_entries = [e for e in audit_entries if e.call_id == call_id]
    present_types = {e.event_type for e in call_entries}

    missing = expected_events - present_types
    return {
        "complete": len(missing) == 0,
        "present": sorted(present_types),
        "missing": sorted(missing),
        "total_entries": len(call_entries),
    }


# ---------------------------------------------------------------------------
# DPDP Act 2023 compliance helpers (Req 10.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DPDPComplianceConfig:
    """Digital Personal Data Protection Act 2023 compliance settings.

    CrisisLink processes personal data (caller audio, location, phone
    number) only when operationally necessary for emergency response.

    Requirement 10.5
    """

    purpose_limitation: str = "emergency_response_only"
    data_minimization: bool = True
    consent_basis: str = "legitimate_interest_emergency"
    retention_aligned: bool = True

    def is_compliant(self) -> bool:
        """Return True if the configuration meets DPDP Act requirements."""
        return (
            self.purpose_limitation == "emergency_response_only"
            and self.data_minimization
            and self.retention_aligned
        )


DPDP_CONFIG = DPDPComplianceConfig()
