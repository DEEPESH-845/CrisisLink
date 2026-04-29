"""Integration tests for CrisisLink end-to-end pipeline wiring.

Verifies:
- Pipeline stages are connected correctly (Task 13.1)
- Operator Dashboard wiring (Task 13.2)
- Responder App wiring (Task 13.3)
- Security configuration and data retention (Task 13.4)
- Audit log entries are produced at each stage

Requirements: 1.4, 2.4, 4.4, 4.5, 5.1, 5.4, 6.1–6.7, 7.1, 7.5, 7.6,
              8.1, 8.3, 10.1, 10.2, 10.4, 10.5
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from shared.models import (
    AuditEventType,
    CallerRole,
    CallerState,
    DispatchCard,
    DispatchRecommendation,
    EmergencyClassification,
    EmergencyType,
    Location,
    PanicLevel,
    Severity,
    UnitStatus,
)
from speech_ingestion.audit_logger import AuditEntry, MockAuditLogger

from integration.pipeline import (
    CallPipeline,
    PipelineStage,
    _log_pipeline_audit,
)
from integration.operator_wiring import (
    ClassificationOverrideResult,
    DispatchConfirmationResult,
    get_dashboard_paths,
    handle_dispatch_confirmation,
    log_classification_override,
    OPERATOR_DASHBOARD_SUBSCRIPTIONS,
)
from integration.responder_wiring import (
    GPS_STALENESS_THRESHOLD_SECONDS,
    GPS_UPDATE_INTERVAL_SECONDS,
    VALID_STATUS_TRANSITIONS,
    is_valid_transition,
    process_gps_update,
    propagate_status_update,
    trigger_dispatch_notification,
)
from integration.security import (
    DATA_RETENTION_POLICY,
    DPDP_CONFIG,
    ENCRYPTION_CONFIG,
    DataRetentionPolicy,
    EncryptionAlgorithm,
    EncryptionConfig,
    SessionCleanupResult,
    TransportProtocol,
    cleanup_session_data,
    verify_audit_completeness,
)


# ---------------------------------------------------------------------------
# Helpers / Mocks
# ---------------------------------------------------------------------------


def _make_classification(
    call_id: str = "call-001",
    severity: Severity = Severity.CRITICAL,
    emergency_type: EmergencyType = EmergencyType.MEDICAL,
    confidence: float = 0.9,
) -> EmergencyClassification:
    return EmergencyClassification(
        call_id=call_id,
        emergency_type=emergency_type,
        severity=severity,
        caller_state=CallerState(
            panic_level=PanicLevel.PANIC_HIGH,
            caller_role=CallerRole.VICTIM,
        ),
        language_detected="hi",
        key_facts=["chest pain", "elderly person"],
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
        model_version="gemini-1.5-pro",
    )


def _make_dispatch_card(call_id: str = "call-001") -> DispatchCard:
    return DispatchCard(
        call_id=call_id,
        recommendations=[
            DispatchRecommendation(
                unit_id="AMB_001",
                unit_type="ambulance",
                hospital_or_station="City Hospital",
                eta_minutes=5.0,
                capability_match=0.9,
                composite_score=0.36,
                distance_km=3.0,
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        classification_ref=f"{call_id}/ref",
    )


class MockFirebaseRTDB:
    """Mock Firebase RTDB that records all writes."""

    def __init__(self) -> None:
        self.writes: dict[str, Any] = {}

    def write(self, path: str, data: Any) -> None:
        self.writes[path] = data


class MockSpeechIngestion:
    """Mock speech ingestion that returns a fixed transcript."""

    def __init__(self, transcript: str = "Help, there is a fire") -> None:
        self._transcript = transcript

    def ingest_audio(self, call_id: str, audio_data: bytes) -> str:
        return self._transcript


class MockIntelligence:
    """Mock intelligence service."""

    def __init__(
        self,
        classification: EmergencyClassification | None = None,
        guidance: str = "Stay calm. Help is on the way.",
    ) -> None:
        self._classification = classification or _make_classification()
        self._guidance = guidance

    def classify(self, call_id: str, transcript: str) -> EmergencyClassification:
        return self._classification

    def generate_guidance(
        self,
        call_id: str,
        classification: EmergencyClassification,
        caller_state: CallerState,
    ) -> str:
        return self._guidance


class MockDispatch:
    """Mock dispatch service."""

    def __init__(self, card: DispatchCard | None = None) -> None:
        self._card = card or _make_dispatch_card()

    async def recommend(
        self,
        call_id: str,
        classification: EmergencyClassification,
        caller_location: Location,
    ) -> DispatchCard:
        return self._card


class MockTTS:
    """Mock TTS service."""

    def __init__(self, audio: bytes | None = b"\xff\xfb\x90\x00audio") -> None:
        self._audio = audio

    async def synthesize(self, text: str, language: str) -> bytes | None:
        return self._audio


class MockTelephony:
    """Mock telephony bridge."""

    def __init__(self) -> None:
        self.sent_audio: list[tuple[str, bytes]] = []

    async def send_audio(self, call_id: str, audio: bytes) -> bool:
        self.sent_audio.append((call_id, audio))
        return True


class MockDispatchHandler:
    """Mock dispatch confirmation handler."""

    def __init__(self) -> None:
        self.confirmations: list[tuple[str, str]] = []

    async def confirm(self, call_id: str, unit_id: str) -> dict[str, str]:
        self.confirmations.append((call_id, unit_id))
        return {"status": "dispatched", "unit_id": unit_id}


class MockFCMNotifier:
    """Mock FCM notifier."""

    def __init__(self, should_succeed: bool = True) -> None:
        self._should_succeed = should_succeed
        self.notifications: list[dict[str, Any]] = []

    async def send_dispatch_notification(
        self, unit_id: str, call_id: str, payload: dict[str, Any]
    ) -> bool:
        self.notifications.append(
            {"unit_id": unit_id, "call_id": call_id, "payload": payload}
        )
        return self._should_succeed


# ===================================================================
# Task 13.1 — Pipeline wiring tests
# ===================================================================


class TestCallPipeline:
    """Tests for the end-to-end CallPipeline orchestrator."""

    def _build_pipeline(
        self,
        speech: MockSpeechIngestion | None = None,
        intelligence: MockIntelligence | None = None,
        dispatch: MockDispatch | None = None,
        tts: MockTTS | None = None,
        telephony: MockTelephony | None = None,
        firebase: MockFirebaseRTDB | None = None,
        audit: MockAuditLogger | None = None,
    ) -> tuple[CallPipeline, MockFirebaseRTDB, MockAuditLogger, MockTelephony]:
        fb = firebase or MockFirebaseRTDB()
        al = audit or MockAuditLogger()
        tel = telephony or MockTelephony()
        pipeline = CallPipeline(
            speech=speech or MockSpeechIngestion(),
            intelligence=intelligence or MockIntelligence(),
            dispatch=dispatch or MockDispatch(),
            tts=tts or MockTTS(),
            telephony=tel,
            firebase=fb,
            audit_logger=al,
        )
        return pipeline, fb, al, tel

    @pytest.mark.asyncio
    async def test_full_pipeline_all_stages_complete(self):
        """All five stages complete for a CRITICAL severity call."""
        pipeline, fb, audit, tel = self._build_pipeline()
        location = Location(lat=28.6139, lng=77.2090)

        result = await pipeline.process_audio_chunk(
            "call-001", b"audio-data", location
        )

        assert PipelineStage.SPEECH_INGESTION in result.stages_completed
        assert PipelineStage.CLASSIFICATION in result.stages_completed
        assert PipelineStage.DISPATCH in result.stages_completed
        assert PipelineStage.GUIDANCE in result.stages_completed
        assert PipelineStage.TTS in result.stages_completed
        assert result.errors == {}

    @pytest.mark.asyncio
    async def test_transcript_written_to_firebase(self):
        """Speech ingestion writes transcript to RTDB (Req 1.4)."""
        pipeline, fb, _, _ = self._build_pipeline()
        location = Location(lat=28.6139, lng=77.2090)

        await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert "/calls/call-001/transcript" in fb.writes
        assert "text" in fb.writes["/calls/call-001/transcript"]

    @pytest.mark.asyncio
    async def test_classification_written_to_firebase(self):
        """Classification writes to RTDB (Req 2.4)."""
        pipeline, fb, _, _ = self._build_pipeline()
        location = Location(lat=28.6139, lng=77.2090)

        await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert "/calls/call-001/classification" in fb.writes
        data = fb.writes["/calls/call-001/classification"]
        assert data["emergency_type"] == "MEDICAL"

    @pytest.mark.asyncio
    async def test_dispatch_card_written_to_firebase(self):
        """Dispatch card writes to RTDB (Req 4.4)."""
        pipeline, fb, _, _ = self._build_pipeline()
        location = Location(lat=28.6139, lng=77.2090)

        await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert "/calls/call-001/dispatch_card" in fb.writes
        data = fb.writes["/calls/call-001/dispatch_card"]
        assert len(data["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_guidance_written_to_firebase(self):
        """Guidance writes to RTDB (Req 5.4)."""
        pipeline, fb, _, _ = self._build_pipeline()
        location = Location(lat=28.6139, lng=77.2090)

        await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert "/calls/call-001/guidance" in fb.writes
        data = fb.writes["/calls/call-001/guidance"]
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_tts_audio_sent_to_caller(self):
        """TTS audio is sent back through telephony bridge."""
        tel = MockTelephony()
        pipeline, _, _, _ = self._build_pipeline(telephony=tel)
        location = Location(lat=28.6139, lng=77.2090)

        result = await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert result.audio_sent_to_caller is True
        assert len(tel.sent_audio) == 1
        assert tel.sent_audio[0][0] == "call-001"

    @pytest.mark.asyncio
    async def test_audit_entries_at_each_stage(self):
        """Audit log entries are produced at each pipeline stage (Req 10.4)."""
        pipeline, _, audit, _ = self._build_pipeline()
        location = Location(lat=28.6139, lng=77.2090)

        await pipeline.process_audio_chunk("call-001", b"audio", location)

        event_types = {e.event_type for e in audit.entries}
        assert PipelineStage.SPEECH_INGESTION.value in event_types
        assert PipelineStage.CLASSIFICATION.value in event_types
        assert PipelineStage.DISPATCH.value in event_types
        assert PipelineStage.GUIDANCE.value in event_types
        assert PipelineStage.TTS.value in event_types

    @pytest.mark.asyncio
    async def test_no_guidance_for_low_severity(self):
        """Guidance is skipped for MODERATE severity (Req 5.1)."""
        classification = _make_classification(severity=Severity.MODERATE)
        intelligence = MockIntelligence(classification=classification)
        pipeline, fb, _, _ = self._build_pipeline(intelligence=intelligence)
        location = Location(lat=28.6139, lng=77.2090)

        result = await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert PipelineStage.GUIDANCE not in result.stages_completed
        assert PipelineStage.TTS not in result.stages_completed
        assert "/calls/call-001/guidance" not in fb.writes

    @pytest.mark.asyncio
    async def test_pipeline_graceful_degradation_on_dispatch_error(self):
        """Pipeline continues if dispatch fails (graceful degradation)."""

        class FailingDispatch:
            async def recommend(self, *args, **kwargs):
                raise RuntimeError("Maps API down")

        pipeline, _, _, _ = self._build_pipeline(dispatch=FailingDispatch())
        location = Location(lat=28.6139, lng=77.2090)

        result = await pipeline.process_audio_chunk("call-001", b"audio", location)

        assert PipelineStage.SPEECH_INGESTION in result.stages_completed
        assert PipelineStage.CLASSIFICATION in result.stages_completed
        assert PipelineStage.DISPATCH.value in result.errors
        # Guidance + TTS should still run
        assert PipelineStage.GUIDANCE in result.stages_completed


# ===================================================================
# Task 13.2 — Operator Dashboard wiring tests
# ===================================================================


class TestOperatorDashboardWiring:
    """Tests for Operator Dashboard ↔ backend wiring."""

    def test_dashboard_paths_are_correct(self):
        """Dashboard subscribes to the correct RTDB paths (Req 6.1)."""
        paths = get_dashboard_paths("call-123")

        assert paths["transcript"] == "/calls/call-123/transcript"
        assert paths["classification"] == "/calls/call-123/classification"
        assert paths["dispatch_card"] == "/calls/call-123/dispatch_card"
        assert paths["guidance"] == "/calls/call-123/guidance"

    def test_all_subscription_templates_defined(self):
        """All five dashboard subscriptions are defined (Req 6.2)."""
        assert "transcript" in OPERATOR_DASHBOARD_SUBSCRIPTIONS
        assert "classification" in OPERATOR_DASHBOARD_SUBSCRIPTIONS
        assert "dispatch_card" in OPERATOR_DASHBOARD_SUBSCRIPTIONS
        assert "guidance" in OPERATOR_DASHBOARD_SUBSCRIPTIONS

    @pytest.mark.asyncio
    async def test_dispatch_confirmation_flow(self):
        """Dispatch confirmation triggers service + RTDB write + audit (Req 6.3, 6.4)."""
        handler = MockDispatchHandler()
        firebase = MockFirebaseRTDB()
        audit = MockAuditLogger()

        result = await handle_dispatch_confirmation(
            call_id="call-001",
            unit_id="AMB_001",
            dispatch_handler=handler,
            firebase=firebase,
            audit_logger=audit,
        )

        assert result.status == "dispatched"
        assert result.unit_status_updated is True
        assert result.audit_logged is True
        assert "/calls/call-001/confirmed_unit" in firebase.writes
        assert firebase.writes["/calls/call-001/confirmed_unit"] == "AMB_001"
        assert len(handler.confirmations) == 1

    @pytest.mark.asyncio
    async def test_dispatch_confirmation_audit_entry(self):
        """Dispatch confirmation produces a BigQuery audit entry (Req 10.4)."""
        handler = MockDispatchHandler()
        firebase = MockFirebaseRTDB()
        audit = MockAuditLogger()

        await handle_dispatch_confirmation(
            "call-001", "AMB_001", handler, firebase, audit
        )

        assert len(audit.entries) == 1
        entry = audit.entries[0]
        assert entry.call_id == "call-001"
        assert entry.event_type == AuditEventType.DISPATCH.value
        assert entry.payload["unit_id"] == "AMB_001"

    def test_classification_override_audit_log(self):
        """Classification override writes to BigQuery audit (Req 6.7, 10.4)."""
        audit = MockAuditLogger()

        result = log_classification_override(
            call_id="call-001",
            operator_id="operator-42",
            original_type="MEDICAL",
            override_type="ACCIDENT",
            original_severity="HIGH",
            override_severity="CRITICAL",
            audit_logger=audit,
        )

        assert result.audit_logged is True
        assert len(audit.entries) == 1
        entry = audit.entries[0]
        assert entry.event_type == AuditEventType.OPERATOR_OVERRIDE.value
        assert entry.payload["operator_id"] == "operator-42"
        assert entry.payload["original_emergency_type"] == "MEDICAL"
        assert entry.payload["override_emergency_type"] == "ACCIDENT"


# ===================================================================
# Task 13.3 — Responder App wiring tests
# ===================================================================


class TestResponderAppWiring:
    """Tests for Responder App ↔ backend wiring."""

    @pytest.mark.asyncio
    async def test_fcm_notification_on_dispatch(self):
        """Dispatch confirmation triggers FCM push notification (Req 4.5, 7.1)."""
        notifier = MockFCMNotifier()

        result = await trigger_dispatch_notification(
            unit_id="AMB_001",
            call_id="call-001",
            emergency_type="MEDICAL",
            severity="CRITICAL",
            caller_location={"lat": 28.6139, "lng": 77.2090},
            fcm_notifier=notifier,
        )

        assert result.sent is True
        assert len(notifier.notifications) == 1
        payload = notifier.notifications[0]["payload"]
        assert payload["emergency_type"] == "MEDICAL"
        assert payload["severity"] == "CRITICAL"
        assert payload["caller_location"]["lat"] == 28.6139

    @pytest.mark.asyncio
    async def test_fcm_notification_failure_handled(self):
        """FCM failure is recorded without crashing (Req 7.1)."""
        notifier = MockFCMNotifier(should_succeed=False)

        result = await trigger_dispatch_notification(
            unit_id="AMB_001",
            call_id="call-001",
            emergency_type="FIRE",
            severity="HIGH",
            caller_location={"lat": 28.0, "lng": 77.0},
            fcm_notifier=notifier,
        )

        assert result.sent is False

    def test_valid_status_transitions(self):
        """Only valid status transitions are accepted (Req 7.4, 8.2)."""
        assert is_valid_transition(UnitStatus.AVAILABLE, UnitStatus.DISPATCHED)
        assert is_valid_transition(UnitStatus.DISPATCHED, UnitStatus.ON_SCENE)
        assert is_valid_transition(UnitStatus.ON_SCENE, UnitStatus.RETURNING)
        assert is_valid_transition(UnitStatus.RETURNING, UnitStatus.AVAILABLE)

    def test_invalid_status_transitions_rejected(self):
        """Invalid transitions are rejected (Req 7.4, 8.2)."""
        assert not is_valid_transition(UnitStatus.AVAILABLE, UnitStatus.ON_SCENE)
        assert not is_valid_transition(UnitStatus.DISPATCHED, UnitStatus.AVAILABLE)
        assert not is_valid_transition(UnitStatus.ON_SCENE, UnitStatus.DISPATCHED)
        assert not is_valid_transition(UnitStatus.RETURNING, UnitStatus.ON_SCENE)

    def test_status_update_propagation(self):
        """Valid status update writes to Firebase RTDB (Req 7.5)."""
        firebase = MockFirebaseRTDB()

        result = propagate_status_update(
            unit_id="AMB_001",
            current_status=UnitStatus.AVAILABLE,
            new_status=UnitStatus.DISPATCHED,
            firebase=firebase,
        )

        assert result.accepted is True
        assert result.firebase_written is True
        assert firebase.writes["/units/AMB_001/status"] == "dispatched"

    def test_invalid_status_update_rejected(self):
        """Invalid status update is rejected without writing (Req 7.4)."""
        firebase = MockFirebaseRTDB()

        result = propagate_status_update(
            unit_id="AMB_001",
            current_status=UnitStatus.AVAILABLE,
            new_status=UnitStatus.ON_SCENE,
            firebase=firebase,
        )

        assert result.accepted is False
        assert result.firebase_written is False
        assert result.error is not None
        assert len(firebase.writes) == 0

    def test_gps_update_writes_to_firebase(self):
        """GPS update writes location to RTDB (Req 8.1, 8.3)."""
        firebase = MockFirebaseRTDB()

        update = process_gps_update(
            unit_id="AMB_001",
            lat=28.6139,
            lng=77.2090,
            firebase=firebase,
            timestamp=time.time(),
        )

        assert update.is_stale is False
        assert "/units/AMB_001/location" in firebase.writes
        loc = firebase.writes["/units/AMB_001/location"]
        assert loc["lat"] == 28.6139
        assert loc["lng"] == 77.2090

    def test_stale_gps_update_detected(self):
        """GPS update older than 60s is marked stale."""
        firebase = MockFirebaseRTDB()
        old_timestamp = time.time() - GPS_STALENESS_THRESHOLD_SECONDS - 10

        update = process_gps_update(
            unit_id="AMB_001",
            lat=28.0,
            lng=77.0,
            firebase=firebase,
            timestamp=old_timestamp,
        )

        assert update.is_stale is True

    def test_gps_update_interval_constant(self):
        """GPS update interval is 10 seconds (Req 7.6, 8.1)."""
        assert GPS_UPDATE_INTERVAL_SECONDS == 10


# ===================================================================
# Task 13.4 — Security configuration tests
# ===================================================================


class TestSecurityConfiguration:
    """Tests for encryption, audit logging, and data retention."""

    def test_encryption_at_rest_aes256(self):
        """AES-256 encryption at rest is configured (Req 10.1)."""
        assert ENCRYPTION_CONFIG.at_rest_algorithm == EncryptionAlgorithm.AES_256_GCM

    def test_encryption_in_transit_tls13(self):
        """TLS 1.3 in transit is configured (Req 10.1)."""
        assert ENCRYPTION_CONFIG.in_transit_protocol == TransportProtocol.TLS_1_3

    def test_encryption_covers_audio_and_transcripts(self):
        """Both audio and transcripts are encrypted (Req 10.1)."""
        assert ENCRYPTION_CONFIG.audio_encrypted is True
        assert ENCRYPTION_CONFIG.transcript_encrypted is True

    def test_encryption_config_is_compliant(self):
        """Full encryption config passes compliance check."""
        assert ENCRYPTION_CONFIG.is_compliant() is True

    def test_non_compliant_encryption_detected(self):
        """Non-compliant encryption config is detected."""
        bad_config = EncryptionConfig(audio_encrypted=False)
        assert bad_config.is_compliant() is False

    def test_raw_audio_discarded_at_session_end(self):
        """Raw audio is discarded at session end (Req 10.2)."""
        assert DATA_RETENTION_POLICY.raw_audio_policy == "discard_at_session_end"

    def test_transcript_retention_90_days(self):
        """Transcripts are retained for 90 days (Req 10.2)."""
        assert DATA_RETENTION_POLICY.transcript_retention_days == 90

    def test_data_retention_policy_is_compliant(self):
        """Default retention policy passes compliance check."""
        assert DATA_RETENTION_POLICY.is_compliant() is True

    def test_non_compliant_retention_detected(self):
        """Retention > 90 days is non-compliant."""
        bad_policy = DataRetentionPolicy(transcript_retention_days=180)
        assert bad_policy.is_compliant() is False

    def test_session_cleanup_discards_audio(self):
        """Session cleanup clears the audio buffer (Req 10.2)."""
        audio_buffer = [b"chunk1", b"chunk2", b"chunk3"]

        result = cleanup_session_data("call-001", audio_buffer=audio_buffer)

        assert result.audio_discarded is True
        assert len(audio_buffer) == 0  # buffer cleared in-place

    def test_session_cleanup_marks_transcript_retention(self):
        """Session cleanup sets transcript retention expiry."""
        result = cleanup_session_data("call-001")

        assert result.transcript_marked_for_retention is True
        assert result.retention_expiry is not None

    def test_audit_completeness_verification(self):
        """Audit completeness check identifies present and missing events (Req 10.4)."""
        entries = [
            AuditEntry(
                call_id="call-001",
                event_type=AuditEventType.CLASSIFICATION.value,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        result = verify_audit_completeness(
            "call-001",
            entries,
            expected_events={
                AuditEventType.CLASSIFICATION.value,
                AuditEventType.DISPATCH.value,
            },
        )

        assert result["complete"] is False
        assert AuditEventType.CLASSIFICATION.value in result["present"]
        assert AuditEventType.DISPATCH.value in result["missing"]

    def test_audit_completeness_all_present(self):
        """Audit completeness passes when all expected events exist."""
        entries = [
            AuditEntry(
                call_id="call-001",
                event_type=AuditEventType.CLASSIFICATION.value,
                timestamp=datetime.now(timezone.utc),
            ),
            AuditEntry(
                call_id="call-001",
                event_type=AuditEventType.DISPATCH.value,
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        result = verify_audit_completeness("call-001", entries)

        assert result["complete"] is True
        assert result["missing"] == []

    def test_dpdp_compliance_config(self):
        """DPDP Act 2023 compliance config is correct (Req 10.5)."""
        assert DPDP_CONFIG.purpose_limitation == "emergency_response_only"
        assert DPDP_CONFIG.data_minimization is True
        assert DPDP_CONFIG.is_compliant() is True
