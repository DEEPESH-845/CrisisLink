"""End-to-end Call Pipeline Orchestrator.

Wires the four core backend services into a single streaming pipeline:

    Audio → Speech Ingestion → Firebase RTDB transcript
        → Intelligence Engine (classification + guidance)
            → Dispatch Engine (ranked recommendations)
            → TTS Service (spoken guidance → Telephony Bridge)

Firebase RTDB acts as the message bus between services.  Each stage
writes audit log entries to BigQuery for compliance (Requirement 10.4).

Requirements: 1.4, 2.4, 4.4, 5.1, 5.4, 10.4
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from shared.firebase.paths import (
    call_classification,
    call_dispatch_card,
    call_guidance,
    call_transcript,
)
from shared.models import (
    AuditEventType,
    CallerState,
    DispatchCard,
    EmergencyClassification,
    Location,
    Severity,
)
from speech_ingestion.audit_logger import AuditEntry, AuditLogger, MockAuditLogger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stage enum
# ---------------------------------------------------------------------------


class PipelineStage(str, Enum):
    """Identifies each stage in the call processing pipeline."""

    SPEECH_INGESTION = "speech_ingestion"
    CLASSIFICATION = "classification"
    DISPATCH = "dispatch"
    GUIDANCE = "guidance"
    TTS = "tts"


# ---------------------------------------------------------------------------
# Service protocols — thin abstractions over the real service modules
# ---------------------------------------------------------------------------


@runtime_checkable
class SpeechIngestionService(Protocol):
    """Accepts raw audio and returns a transcript."""

    def ingest_audio(self, call_id: str, audio_data: bytes) -> str:
        """Process audio and return the rolling transcript text."""
        ...


@runtime_checkable
class IntelligenceService(Protocol):
    """Classifies a transcript and generates guidance."""

    def classify(self, call_id: str, transcript: str) -> EmergencyClassification:
        """Return an EmergencyClassification for the transcript."""
        ...

    def generate_guidance(
        self,
        call_id: str,
        classification: EmergencyClassification,
        caller_state: CallerState,
    ) -> str:
        """Return guidance text (empty string if severity too low)."""
        ...


@runtime_checkable
class DispatchService(Protocol):
    """Produces ranked dispatch recommendations."""

    async def recommend(
        self,
        call_id: str,
        classification: EmergencyClassification,
        caller_location: Location,
    ) -> DispatchCard:
        """Return a DispatchCard with ranked recommendations."""
        ...


@runtime_checkable
class TTSService(Protocol):
    """Synthesises guidance text into audio."""

    async def synthesize(self, text: str, language: str) -> bytes | None:
        """Return audio bytes, or None on failure."""
        ...


@runtime_checkable
class TelephonyBridge(Protocol):
    """Sends audio back to the caller."""

    async def send_audio(self, call_id: str, audio: bytes) -> bool:
        """Stream audio to the caller. Returns True on success."""
        ...


@runtime_checkable
class FirebaseRTDB(Protocol):
    """Writes data to Firebase Realtime Database paths."""

    def write(self, path: str, data: Any) -> None:
        """Set *data* at *path* in RTDB."""
        ...


# ---------------------------------------------------------------------------
# Pipeline audit helper
# ---------------------------------------------------------------------------


def _log_pipeline_audit(
    audit_logger: AuditLogger,
    call_id: str,
    stage: PipelineStage,
    payload: dict[str, Any],
) -> None:
    """Write an audit log entry for a pipeline stage."""
    entry = AuditEntry(
        call_id=call_id,
        event_type=stage.value,
        timestamp=datetime.now(timezone.utc),
        payload=payload,
    )
    try:
        audit_logger.log(entry)
    except NotImplementedError:
        logger.debug("Audit logger not available for stage %s", stage.value)


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Outcome of a full pipeline run for a single audio chunk."""

    call_id: str
    transcript: str = ""
    classification: EmergencyClassification | None = None
    dispatch_card: DispatchCard | None = None
    guidance_text: str = ""
    tts_audio: bytes | None = None
    audio_sent_to_caller: bool = False
    stages_completed: list[PipelineStage] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CallPipeline — the main orchestrator
# ---------------------------------------------------------------------------


class CallPipeline:
    """Orchestrates the end-to-end call processing pipeline.

    Wires:
    1. Speech Ingestion → Firebase RTDB transcript (Req 1.4)
    2. Intelligence classification from transcript (Req 2.4)
    3. Dispatch recommendation from classification (Req 4.4)
    4. Guidance generation → TTS → Telephony Bridge (Req 5.1, 5.4)
    5. Audit logging at every stage (Req 10.4)

    Parameters
    ----------
    speech : SpeechIngestionService
    intelligence : IntelligenceService
    dispatch : DispatchService
    tts : TTSService
    telephony : TelephonyBridge
    firebase : FirebaseRTDB
    audit_logger : AuditLogger
    """

    def __init__(
        self,
        speech: SpeechIngestionService,
        intelligence: IntelligenceService,
        dispatch: DispatchService,
        tts: TTSService,
        telephony: TelephonyBridge,
        firebase: FirebaseRTDB,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self._speech = speech
        self._intelligence = intelligence
        self._dispatch = dispatch
        self._tts = tts
        self._telephony = telephony
        self._firebase = firebase
        self._audit = audit_logger or MockAuditLogger()

    # ------------------------------------------------------------------
    # Full pipeline execution
    # ------------------------------------------------------------------

    async def process_audio_chunk(
        self,
        call_id: str,
        audio_data: bytes,
        caller_location: Location,
    ) -> PipelineResult:
        """Run the full pipeline for a single audio chunk.

        Each stage is executed sequentially.  If a stage fails the
        pipeline records the error and continues with subsequent stages
        where possible (graceful degradation per Req 11.6).

        Returns a :class:`PipelineResult` summarising what happened.
        """
        result = PipelineResult(call_id=call_id)

        # Stage 1 — Speech Ingestion → transcript
        transcript = self._run_speech_ingestion(call_id, audio_data, result)
        if not transcript:
            return result

        # Stage 2 — Intelligence → classification
        classification = self._run_classification(call_id, transcript, result)
        if classification is None:
            return result

        # Stage 3 — Dispatch recommendation (async)
        await self._run_dispatch(call_id, classification, caller_location, result)

        # Stage 4 — Guidance + TTS (async, only for CRITICAL/HIGH)
        await self._run_guidance_and_tts(call_id, classification, result)

        return result

    # ------------------------------------------------------------------
    # Individual stage runners
    # ------------------------------------------------------------------

    def _run_speech_ingestion(
        self,
        call_id: str,
        audio_data: bytes,
        result: PipelineResult,
    ) -> str:
        """Stage 1: Ingest audio → produce transcript → write to RTDB."""
        try:
            transcript = self._speech.ingest_audio(call_id, audio_data)
            result.transcript = transcript

            # Write transcript to Firebase RTDB
            self._firebase.write(
                call_transcript(call_id),
                {"text": transcript, "updated_at": datetime.now(timezone.utc).isoformat()},
            )

            _log_pipeline_audit(
                self._audit,
                call_id,
                PipelineStage.SPEECH_INGESTION,
                {"chunks_received": 1, "transcript_length": len(transcript)},
            )
            result.stages_completed.append(PipelineStage.SPEECH_INGESTION)
            return transcript

        except Exception as exc:
            logger.error("Speech ingestion failed for call %s: %s", call_id, exc)
            result.errors[PipelineStage.SPEECH_INGESTION.value] = str(exc)
            return ""

    def _run_classification(
        self,
        call_id: str,
        transcript: str,
        result: PipelineResult,
    ) -> EmergencyClassification | None:
        """Stage 2: Classify transcript → write to RTDB."""
        try:
            classification = self._intelligence.classify(call_id, transcript)
            result.classification = classification

            # Write classification to Firebase RTDB
            self._firebase.write(
                call_classification(call_id),
                classification.model_dump(mode="json"),
            )

            _log_pipeline_audit(
                self._audit,
                call_id,
                PipelineStage.CLASSIFICATION,
                {
                    "emergency_type": classification.emergency_type.value,
                    "severity": classification.severity.value,
                    "confidence": classification.confidence,
                },
            )
            result.stages_completed.append(PipelineStage.CLASSIFICATION)
            return classification

        except Exception as exc:
            logger.error("Classification failed for call %s: %s", call_id, exc)
            result.errors[PipelineStage.CLASSIFICATION.value] = str(exc)
            return None

    async def _run_dispatch(
        self,
        call_id: str,
        classification: EmergencyClassification,
        caller_location: Location,
        result: PipelineResult,
    ) -> None:
        """Stage 3: Generate dispatch recommendations → write to RTDB."""
        try:
            card = await self._dispatch.recommend(
                call_id, classification, caller_location
            )
            result.dispatch_card = card

            # Write dispatch card to Firebase RTDB
            self._firebase.write(
                call_dispatch_card(call_id),
                card.model_dump(mode="json"),
            )

            _log_pipeline_audit(
                self._audit,
                call_id,
                PipelineStage.DISPATCH,
                {"recommendations_count": len(card.recommendations)},
            )
            result.stages_completed.append(PipelineStage.DISPATCH)

        except Exception as exc:
            logger.error("Dispatch failed for call %s: %s", call_id, exc)
            result.errors[PipelineStage.DISPATCH.value] = str(exc)

    async def _run_guidance_and_tts(
        self,
        call_id: str,
        classification: EmergencyClassification,
        result: PipelineResult,
    ) -> None:
        """Stage 4: Generate guidance → TTS → send audio to caller."""
        # Only generate guidance for CRITICAL or HIGH severity (Req 5.1)
        if classification.severity not in (Severity.CRITICAL, Severity.HIGH):
            return

        try:
            guidance_text = self._intelligence.generate_guidance(
                call_id, classification, classification.caller_state
            )
            result.guidance_text = guidance_text

            if not guidance_text:
                return

            # Write guidance status to Firebase RTDB
            self._firebase.write(
                call_guidance(call_id),
                {
                    "status": "active",
                    "language": classification.language_detected,
                    "text": guidance_text,
                },
            )

            _log_pipeline_audit(
                self._audit,
                call_id,
                PipelineStage.GUIDANCE,
                {"language": classification.language_detected, "text_length": len(guidance_text)},
            )
            result.stages_completed.append(PipelineStage.GUIDANCE)

        except Exception as exc:
            logger.error("Guidance generation failed for call %s: %s", call_id, exc)
            result.errors[PipelineStage.GUIDANCE.value] = str(exc)
            return

        # TTS synthesis and telephony relay
        try:
            audio = await self._tts.synthesize(
                guidance_text, classification.language_detected
            )
            result.tts_audio = audio

            if audio:
                sent = await self._telephony.send_audio(call_id, audio)
                result.audio_sent_to_caller = sent

            _log_pipeline_audit(
                self._audit,
                call_id,
                PipelineStage.TTS,
                {
                    "audio_produced": audio is not None,
                    "audio_sent": result.audio_sent_to_caller,
                },
            )
            result.stages_completed.append(PipelineStage.TTS)

        except Exception as exc:
            logger.error("TTS/telephony failed for call %s: %s", call_id, exc)
            result.errors[PipelineStage.TTS.value] = str(exc)
