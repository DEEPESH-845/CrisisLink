"""Business logic for the Intelligence Service.

Provides emergency classification via Gemini 1.5 Pro (with protocol/mock
pattern for testing) and stub guidance generation. Classification results
are written to Firebase RTDB via a ClassificationWriter.

After classification:
- Confidence < 0.7 flags the call for manual operator takeover (Req 2.6, 6.6)
- An audit log entry is written to BigQuery for every classification (Req 10.4)
- Timeout monitoring alerts the Operator Dashboard if classification
  takes longer than 8 seconds (Req 11.4)

Error handling:
- Gemini timeout (> 5s): retry once with truncated transcript
- Invalid JSON response: retry once with explicit JSON instruction
- API quota exceeded (HTTP 429): exponential backoff up to 3 retries

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 5.1, 6.6, 10.4, 11.4
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.models import (
    AuditEventType,
    CallerRole,
    CallerState,
    EmergencyClassification,
    EmergencyType,
    PanicLevel,
    Severity,
)
from speech_ingestion.audit_logger import AuditEntry, AuditLogger, MockAuditLogger

from .confidence_flagging import (
    flag_call_for_manual_takeover,
    should_flag_for_manual_takeover,
)
from .firebase_classifier_writer import ClassificationWriter, MockClassificationWriter
from .firebase_guidance_writer import (
    GuidanceWriter,
    MockGuidanceWriter,
    write_guidance_to_firebase,
)
from .gemini_classifier import (
    ClassificationResult,
    GeminiClassifier,
    GeminiInvalidJSONError,
    GeminiQuotaExceededError,
    GeminiTimeoutError,
    MockGeminiClassifier,
)
from .guidance_generator import (
    generate_guidance_text,
    select_guidance_protocol,
    select_guidance_register,
    should_generate_guidance,
)
from .timeout_monitor import (
    ClassificationTimeoutMonitor,
    check_and_alert_timeout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level dependencies (injectable for testing)
# ---------------------------------------------------------------------------

_classifier: GeminiClassifier = MockGeminiClassifier()
_writer: ClassificationWriter = MockClassificationWriter()
_audit_logger: AuditLogger = MockAuditLogger()

# Maximum transcript length (characters) for retry on timeout.
_TRUNCATED_TRANSCRIPT_LENGTH = 500

# Exponential backoff settings for quota exceeded errors.
_QUOTA_MAX_RETRIES = 3
_QUOTA_BASE_DELAY_SECONDS = 1.0


def configure(
    classifier: GeminiClassifier | None = None,
    writer: ClassificationWriter | None = None,
    audit_logger: AuditLogger | None = None,
) -> None:
    """Inject dependencies for the intelligence service.

    Call this at application startup to wire in production or test
    implementations of the classifier, writer, and audit logger.
    """
    global _classifier, _writer, _audit_logger
    if classifier is not None:
        _classifier = classifier
    if writer is not None:
        _writer = writer
    if audit_logger is not None:
        _audit_logger = audit_logger


def get_classifier() -> GeminiClassifier:
    """Return the currently configured classifier (useful for tests)."""
    return _classifier


def get_writer() -> ClassificationWriter:
    """Return the currently configured writer (useful for tests)."""
    return _writer


def get_audit_logger() -> AuditLogger:
    """Return the currently configured audit logger (useful for tests)."""
    return _audit_logger


# ---------------------------------------------------------------------------
# Classification pipeline
# ---------------------------------------------------------------------------


def _parse_classification(
    call_id: str,
    raw: dict[str, Any],
    model_version: str,
) -> EmergencyClassification:
    """Parse raw Gemini JSON output into an EmergencyClassification model.

    Applies defaults for missing optional fields and validates enum values
    via Pydantic.
    """
    caller_state_raw = raw.get("caller_state", {})
    return EmergencyClassification(
        call_id=call_id,
        emergency_type=EmergencyType(raw.get("emergency_type", "UNKNOWN")),
        severity=Severity(raw.get("severity", "MODERATE")),
        caller_state=CallerState(
            panic_level=PanicLevel(caller_state_raw.get("panic_level", "CALM")),
            caller_role=CallerRole(caller_state_raw.get("caller_role", "BYSTANDER")),
        ),
        language_detected=raw.get("language_detected", "hi"),
        key_facts=raw.get("key_facts", []),
        confidence=float(raw.get("confidence", 0.5)),
        timestamp=datetime.now(timezone.utc),
        model_version=model_version,
    )


def _write_results(call_id: str, classification: EmergencyClassification) -> None:
    """Write classification and caller state to Firebase RTDB via the writer."""
    classification_data = classification.model_dump(mode="json")
    caller_state_data = classification.caller_state.model_dump(mode="json")

    try:
        _writer.write_classification(call_id, classification_data)
    except NotImplementedError:
        logger.debug(
            "Classification writer not available (expected in dev/test): %s",
            call_id,
        )

    try:
        _writer.write_caller_state(call_id, caller_state_data)
    except NotImplementedError:
        logger.debug(
            "Caller state writer not available (expected in dev/test): %s",
            call_id,
        )


def _classify_with_retry(
    call_id: str,
    transcript: str,
) -> ClassificationResult:
    """Call the Gemini classifier with retry logic for known error modes.

    Retry strategy:
    1. Timeout (> 5s): retry once with truncated transcript.
    2. Invalid JSON: retry once (the classifier prompt already includes
       explicit JSON instructions; the retry gives Gemini a second chance).
    3. Quota exceeded (HTTP 429): exponential backoff, up to 3 retries.

    If all retries are exhausted the original exception is re-raised so
    the caller can fall back to manual handling.
    """
    # --- Attempt 1: normal call ---
    try:
        return _classifier.classify(transcript, call_id)
    except GeminiTimeoutError:
        logger.warning(
            "Gemini timeout for call %s — retrying with truncated transcript",
            call_id,
        )
        truncated = transcript[:_TRUNCATED_TRANSCRIPT_LENGTH]
        return _classifier.classify(truncated, call_id)
    except GeminiInvalidJSONError:
        logger.warning(
            "Gemini returned invalid JSON for call %s — retrying",
            call_id,
        )
        return _classifier.classify(transcript, call_id)
    except GeminiQuotaExceededError:
        logger.warning(
            "Gemini quota exceeded for call %s — starting exponential backoff",
            call_id,
        )
        return _quota_backoff_retry(call_id, transcript)


def _quota_backoff_retry(
    call_id: str,
    transcript: str,
) -> ClassificationResult:
    """Retry classification with exponential backoff on quota errors.

    Retries up to ``_QUOTA_MAX_RETRIES`` times with delays of
    1s, 2s, 4s (base × 2^attempt).
    """
    last_error: GeminiQuotaExceededError | None = None
    for attempt in range(_QUOTA_MAX_RETRIES):
        delay = _QUOTA_BASE_DELAY_SECONDS * (2**attempt)
        logger.info(
            "Quota backoff attempt %d/%d for call %s — waiting %.1fs",
            attempt + 1,
            _QUOTA_MAX_RETRIES,
            call_id,
            delay,
        )
        time.sleep(delay)
        try:
            return _classifier.classify(transcript, call_id)
        except GeminiQuotaExceededError as exc:
            last_error = exc
            continue

    # All retries exhausted — re-raise
    assert last_error is not None
    raise last_error


def classify_transcript(
    call_id: str,
    transcript: str,
    elapsed_seconds: float | None = None,
) -> EmergencyClassification:
    """Produce an ``EmergencyClassification`` from a transcript.

    Calls the configured Gemini classifier with retry logic, parses the
    result, and writes classification + caller state to Firebase RTDB.

    After classification:
    - Checks confidence and flags for manual takeover if < 0.7 (Req 2.6, 6.6)
    - Writes an audit log entry to BigQuery (Req 10.4)
    - Checks classification timeout if *elapsed_seconds* is provided (Req 11.4)

    Falls back to a default UNKNOWN classification if all retries fail.

    Parameters
    ----------
    call_id : str
        Unique call session identifier.
    transcript : str
        The rolling transcript text to classify.
    elapsed_seconds : float | None
        Optional seconds elapsed since the call connected.  When provided,
        the function checks for classification timeout (> 8s) and writes
        a timeout alert to Firebase RTDB if exceeded.
    """
    # Check for classification timeout before attempting classification
    if elapsed_seconds is not None:
        timed_out = check_and_alert_timeout(call_id, elapsed_seconds)
        if timed_out:
            logger.warning(
                "Classification timeout for call %s — returning default classification",
                call_id,
            )
            classification = EmergencyClassification(
                call_id=call_id,
                emergency_type=EmergencyType.UNKNOWN,
                severity=Severity.MODERATE,
                caller_state=CallerState(
                    panic_level=PanicLevel.CALM,
                    caller_role=CallerRole.BYSTANDER,
                ),
                language_detected="hi",
                key_facts=[],
                confidence=0.0,
                timestamp=datetime.now(timezone.utc),
                model_version="timeout-fallback",
            )
            _write_results(call_id, classification)
            _log_classification_audit(call_id, classification, timed_out=True)
            return classification

    try:
        result = _classify_with_retry(call_id, transcript)
        classification = _parse_classification(
            call_id, result.raw_json, result.model_version
        )
    except (GeminiTimeoutError, GeminiInvalidJSONError, GeminiQuotaExceededError) as exc:
        logger.error(
            "All Gemini retries exhausted for call %s: %s — returning default classification",
            call_id,
            exc,
        )
        classification = EmergencyClassification(
            call_id=call_id,
            emergency_type=EmergencyType.UNKNOWN,
            severity=Severity.MODERATE,
            caller_state=CallerState(
                panic_level=PanicLevel.CALM,
                caller_role=CallerRole.BYSTANDER,
            ),
            language_detected="hi",
            key_facts=[],
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            model_version="fallback",
        )

    _write_results(call_id, classification)

    # Confidence threshold flagging (Req 2.6, 6.6)
    if should_flag_for_manual_takeover(classification.confidence):
        flag_call_for_manual_takeover(call_id)

    # Audit logging for all classifications (Req 10.4)
    _log_classification_audit(call_id, classification)

    return classification


def _log_classification_audit(
    call_id: str,
    classification: EmergencyClassification,
    *,
    timed_out: bool = False,
) -> None:
    """Write an audit log entry to BigQuery for a classification event.

    Parameters
    ----------
    call_id : str
        Unique call session identifier.
    classification : EmergencyClassification
        The classification that was produced.
    timed_out : bool
        Whether this classification was produced due to a timeout.
    """
    payload: dict[str, Any] = {
        "emergency_type": classification.emergency_type.value,
        "severity": classification.severity.value,
        "confidence": classification.confidence,
        "model_version": classification.model_version,
        "language_detected": classification.language_detected,
    }
    if timed_out:
        payload["timed_out"] = True

    entry = AuditEntry(
        call_id=call_id,
        event_type=AuditEventType.CLASSIFICATION.value,
        timestamp=datetime.now(timezone.utc),
        payload=payload,
    )
    try:
        _audit_logger.log(entry)
    except NotImplementedError:
        logger.debug(
            "Audit logger not available (expected in dev/test): %s",
            call_id,
        )


def generate_guidance(
    call_id: str,
    classification: EmergencyClassification,
    caller_state: CallerState,
) -> str:
    """Generate caller guidance text based on classification and caller state.

    Uses the Guidance Generator to select the appropriate register
    (communication style) and protocol (content), then generates
    adaptive guidance text. Streams guidance status to Firebase RTDB
    at ``/calls/{call_id}/guidance``.

    Guidance is only generated for severity CRITICAL or HIGH
    (Requirement 5.1).

    Register selection (Requirements 3.4, 3.5, 3.6):
    - PANIC_HIGH + VICTIM → ultra-simple reassurance-first
    - PANIC_HIGH + BYSTANDER → directive numbered steps
    - CALM + BYSTANDER → full clinical protocol
    - All other combinations → default register

    Protocol selection (Requirements 5.6, 5.7):
    - MEDICAL + cardiac indicators → CPR per Indian Resuscitation Council 2022
    - FIRE → NDMA fire evacuation
    - Other types → general guidance protocol

    Parameters
    ----------
    call_id : str
        Unique call session identifier.
    classification : EmergencyClassification
        The emergency classification for the call.
    caller_state : CallerState
        The caller's emotional/cognitive state.

    Returns
    -------
    str
        The generated guidance text, or empty string if severity
        does not warrant guidance.
    """
    if not should_generate_guidance(classification.severity):
        # Write not_applicable status to Firebase
        write_guidance_to_firebase(
            call_id=call_id,
            status="not_applicable",
            language=classification.language_detected,
            protocol_type="",
        )
        return ""

    # Write generating status to Firebase
    protocol = select_guidance_protocol(
        classification.emergency_type,
        classification.key_facts,
    )
    write_guidance_to_firebase(
        call_id=call_id,
        status="generating",
        language=classification.language_detected,
        protocol_type=protocol.value,
    )

    # Generate the guidance text
    guidance_text = generate_guidance_text(classification, caller_state)

    # Write active status with guidance text to Firebase
    write_guidance_to_firebase(
        call_id=call_id,
        status="active",
        language=classification.language_detected,
        protocol_type=protocol.value,
        guidance_text=guidance_text,
    )

    return guidance_text
