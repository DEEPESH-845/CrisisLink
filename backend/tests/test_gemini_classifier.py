"""Tests for the Gemini 1.5 Pro emergency classification pipeline.

Covers:
- MockGeminiClassifier returns valid Emergency_Classification
- System prompt contains India 112 context
- Classification prompt includes transcript text
- Error handling: timeout retry, invalid JSON retry, quota backoff
- Firebase ClassificationWriter records correct paths
- Service-level classify_transcript with dependency injection

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 3.1, 3.2
"""

from __future__ import annotations

import pytest

from intelligence.firebase_classifier_writer import (
    ClassificationWriter,
    FirebaseClassificationWriter,
    MockClassificationWriter,
)
from intelligence.gemini_classifier import (
    ClassificationResult,
    GeminiClassifier,
    GeminiInvalidJSONError,
    GeminiQuotaExceededError,
    GeminiTimeoutError,
    LiveGeminiClassifier,
    MockGeminiClassifier,
)
from intelligence.gemini_prompts import (
    JSON_SCHEMA_INSTRUCTION,
    SYSTEM_PROMPT,
    build_classification_prompt,
)
from intelligence.service import (
    _parse_classification,
    classify_transcript,
    configure,
    get_classifier,
    get_writer,
)
from shared.models import (
    CallerRole,
    EmergencyType,
    PanicLevel,
    Severity,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_service():
    """Reset the intelligence service to default mock dependencies."""
    configure(
        classifier=MockGeminiClassifier(),
        writer=MockClassificationWriter(),
    )
    yield
    configure(
        classifier=MockGeminiClassifier(),
        writer=MockClassificationWriter(),
    )


# -----------------------------------------------------------------------
# Prompt tests
# -----------------------------------------------------------------------


class TestSystemPrompt:
    """System prompt contains India 112 emergency context."""

    def test_mentions_india_112(self):
        assert "112" in SYSTEM_PROMPT
        assert "India" in SYSTEM_PROMPT

    def test_mentions_emergency_triage(self):
        assert "triage" in SYSTEM_PROMPT.lower() or "emergency" in SYSTEM_PROMPT.lower()

    def test_mentions_scheduled_indian_languages(self):
        assert "22 scheduled Indian languages" in SYSTEM_PROMPT

    def test_instructs_json_output(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_lists_classification_fields(self):
        for field_name in [
            "emergency_type",
            "severity",
            "caller_state",
            "language_detected",
            "key_facts",
            "confidence",
        ]:
            assert field_name in SYSTEM_PROMPT


class TestClassificationPrompt:
    """Classification prompt template includes transcript and JSON schema."""

    def test_includes_transcript_text(self):
        transcript = "There is a fire in the building, please help!"
        prompt = build_classification_prompt(transcript)
        assert transcript in prompt

    def test_includes_json_schema_instruction(self):
        prompt = build_classification_prompt("test transcript")
        assert "emergency_type" in prompt
        assert "severity" in prompt
        assert "caller_state" in prompt

    def test_includes_enum_values(self):
        prompt = build_classification_prompt("test")
        for enum_val in ["MEDICAL", "FIRE", "CRIME", "ACCIDENT", "DISASTER", "UNKNOWN"]:
            assert enum_val in prompt
        for sev in ["CRITICAL", "HIGH", "MODERATE", "LOW"]:
            assert sev in prompt

    def test_json_schema_instruction_has_all_fields(self):
        for field_name in [
            "emergency_type",
            "severity",
            "panic_level",
            "caller_role",
            "language_detected",
            "key_facts",
            "confidence",
        ]:
            assert field_name in JSON_SCHEMA_INSTRUCTION


# -----------------------------------------------------------------------
# MockGeminiClassifier tests
# -----------------------------------------------------------------------


class TestMockGeminiClassifier:
    """MockGeminiClassifier returns valid, configurable classifications."""

    def test_returns_classification_result(self):
        classifier = MockGeminiClassifier()
        result = classifier.classify("help me", "CALL-001")
        assert isinstance(result, ClassificationResult)

    def test_default_classification_has_valid_fields(self):
        classifier = MockGeminiClassifier()
        result = classifier.classify("fire in building", "CALL-002")
        raw = result.raw_json
        assert raw["emergency_type"] in [e.value for e in EmergencyType]
        assert raw["severity"] in [s.value for s in Severity]
        assert raw["caller_state"]["panic_level"] in [p.value for p in PanicLevel]
        assert raw["caller_state"]["caller_role"] in [r.value for r in CallerRole]
        assert isinstance(raw["key_facts"], list)
        assert 0.0 <= raw["confidence"] <= 1.0

    def test_custom_classification(self):
        classifier = MockGeminiClassifier(
            emergency_type="FIRE",
            severity="HIGH",
            panic_level="PANIC_MED",
            caller_role="BYSTANDER",
            language_detected="ta",
            key_facts=["smoke visible", "3rd floor"],
            confidence=0.88,
        )
        result = classifier.classify("fire", "CALL-003")
        assert result.raw_json["emergency_type"] == "FIRE"
        assert result.raw_json["severity"] == "HIGH"
        assert result.raw_json["caller_state"]["panic_level"] == "PANIC_MED"
        assert result.raw_json["language_detected"] == "ta"
        assert result.raw_json["confidence"] == 0.88

    def test_tracks_call_count(self):
        classifier = MockGeminiClassifier()
        assert classifier.call_count == 0
        classifier.classify("test", "CALL-004")
        classifier.classify("test2", "CALL-005")
        assert classifier.call_count == 2

    def test_records_last_transcript_and_call_id(self):
        classifier = MockGeminiClassifier()
        classifier.classify("someone collapsed", "CALL-006")
        assert classifier.last_transcript == "someone collapsed"
        assert classifier.last_call_id == "CALL-006"

    def test_satisfies_protocol(self):
        classifier = MockGeminiClassifier()
        assert isinstance(classifier, GeminiClassifier)

    def test_result_includes_model_version(self):
        classifier = MockGeminiClassifier(model_version="gemini-1.5-pro-test")
        result = classifier.classify("test", "CALL-007")
        assert result.model_version == "gemini-1.5-pro-test"

    def test_result_includes_latency(self):
        classifier = MockGeminiClassifier(latency=2.3)
        result = classifier.classify("test", "CALL-008")
        assert result.latency_seconds == 2.3


# -----------------------------------------------------------------------
# Error simulation tests
# -----------------------------------------------------------------------


class TestGeminiErrorSimulation:
    """MockGeminiClassifier can simulate Gemini API errors."""

    def test_raises_timeout_error(self):
        classifier = MockGeminiClassifier(raise_timeout=True)
        with pytest.raises(GeminiTimeoutError):
            classifier.classify("test", "CALL-T1")

    def test_raises_invalid_json_error(self):
        classifier = MockGeminiClassifier(raise_invalid_json=True)
        with pytest.raises(GeminiInvalidJSONError):
            classifier.classify("test", "CALL-J1")

    def test_raises_quota_exceeded_error(self):
        classifier = MockGeminiClassifier(raise_quota_exceeded=True)
        with pytest.raises(GeminiQuotaExceededError):
            classifier.classify("test", "CALL-Q1")


# -----------------------------------------------------------------------
# Error handling / retry tests at the service level
# -----------------------------------------------------------------------


class _TimeoutThenSuccessClassifier:
    """Raises GeminiTimeoutError on first call, succeeds on second."""

    def __init__(self) -> None:
        self.call_count = 0
        self.transcripts: list[str] = []

    def classify(self, transcript: str, call_id: str) -> ClassificationResult:
        self.call_count += 1
        self.transcripts.append(transcript)
        if self.call_count == 1:
            raise GeminiTimeoutError("timeout on first attempt")
        return ClassificationResult(
            raw_json={
                "emergency_type": "ACCIDENT",
                "severity": "HIGH",
                "caller_state": {"panic_level": "PANIC_MED", "caller_role": "WITNESS"},
                "language_detected": "en",
                "key_facts": ["car crash"],
                "confidence": 0.85,
            },
            latency_seconds=3.0,
            model_version="gemini-1.5-pro",
        )


class _InvalidJsonThenSuccessClassifier:
    """Raises GeminiInvalidJSONError on first call, succeeds on second."""

    def __init__(self) -> None:
        self.call_count = 0

    def classify(self, transcript: str, call_id: str) -> ClassificationResult:
        self.call_count += 1
        if self.call_count == 1:
            raise GeminiInvalidJSONError("bad json on first attempt")
        return ClassificationResult(
            raw_json={
                "emergency_type": "CRIME",
                "severity": "MODERATE",
                "caller_state": {"panic_level": "CALM", "caller_role": "WITNESS"},
                "language_detected": "hi",
                "key_facts": ["robbery"],
                "confidence": 0.78,
            },
            latency_seconds=2.0,
            model_version="gemini-1.5-pro",
        )


class _QuotaThenSuccessClassifier:
    """Raises GeminiQuotaExceededError twice, then succeeds."""

    def __init__(self) -> None:
        self.call_count = 0

    def classify(self, transcript: str, call_id: str) -> ClassificationResult:
        self.call_count += 1
        if self.call_count <= 2:
            raise GeminiQuotaExceededError("429 quota exceeded")
        return ClassificationResult(
            raw_json={
                "emergency_type": "MEDICAL",
                "severity": "CRITICAL",
                "caller_state": {"panic_level": "PANIC_HIGH", "caller_role": "VICTIM"},
                "language_detected": "bn",
                "key_facts": ["heart attack"],
                "confidence": 0.95,
            },
            latency_seconds=1.8,
            model_version="gemini-1.5-pro",
        )


class TestTimeoutRetry:
    """Gemini timeout (> 5s) retries with truncated transcript."""

    def test_retries_on_timeout_with_truncated_transcript(self):
        classifier = _TimeoutThenSuccessClassifier()
        writer = MockClassificationWriter()
        configure(classifier=classifier, writer=writer)

        result = classify_transcript("CALL-T2", "A" * 1000)
        assert result.emergency_type == EmergencyType.ACCIDENT
        assert classifier.call_count == 2
        # Second call should have truncated transcript (500 chars)
        assert len(classifier.transcripts[1]) == 500

    def test_falls_back_on_double_timeout(self):
        classifier = MockGeminiClassifier(raise_timeout=True)
        writer = MockClassificationWriter()
        configure(classifier=classifier, writer=writer)

        result = classify_transcript("CALL-T3", "help me")
        # Should fall back to default UNKNOWN classification
        assert result.emergency_type == EmergencyType.UNKNOWN
        assert result.confidence == 0.0
        assert result.model_version == "fallback"


class TestInvalidJsonRetry:
    """Invalid JSON response retries once."""

    def test_retries_on_invalid_json(self):
        classifier = _InvalidJsonThenSuccessClassifier()
        writer = MockClassificationWriter()
        configure(classifier=classifier, writer=writer)

        result = classify_transcript("CALL-J2", "robbery in progress")
        assert result.emergency_type == EmergencyType.CRIME
        assert classifier.call_count == 2

    def test_falls_back_on_double_invalid_json(self):
        classifier = MockGeminiClassifier(raise_invalid_json=True)
        writer = MockClassificationWriter()
        configure(classifier=classifier, writer=writer)

        result = classify_transcript("CALL-J3", "help")
        assert result.emergency_type == EmergencyType.UNKNOWN
        assert result.confidence == 0.0


class TestQuotaBackoff:
    """API quota exceeded (HTTP 429) with exponential backoff."""

    def test_retries_with_backoff_on_quota_exceeded(self):
        classifier = _QuotaThenSuccessClassifier()
        writer = MockClassificationWriter()
        configure(classifier=classifier, writer=writer)

        result = classify_transcript("CALL-Q2", "heart attack")
        assert result.emergency_type == EmergencyType.MEDICAL
        assert result.severity == Severity.CRITICAL
        # 1 initial quota failure + 1 backoff quota failure + 1 backoff success = 3 total
        assert classifier.call_count == 3

    def test_falls_back_after_max_retries(self):
        classifier = MockGeminiClassifier(raise_quota_exceeded=True)
        writer = MockClassificationWriter()
        configure(classifier=classifier, writer=writer)

        result = classify_transcript("CALL-Q3", "emergency")
        assert result.emergency_type == EmergencyType.UNKNOWN
        assert result.confidence == 0.0


# -----------------------------------------------------------------------
# Firebase ClassificationWriter tests
# -----------------------------------------------------------------------


class TestMockClassificationWriter:
    """MockClassificationWriter records writes to correct Firebase paths."""

    def test_satisfies_protocol(self):
        writer = MockClassificationWriter()
        assert isinstance(writer, ClassificationWriter)

    def test_records_classification_write(self):
        writer = MockClassificationWriter()
        data = {"emergency_type": "FIRE", "severity": "HIGH"}
        writer.write_classification("CALL-W1", data)

        assert len(writer.classification_writes) == 1
        record = writer.last_classification()
        assert record is not None
        assert record.call_id == "CALL-W1"
        assert record.path == "/calls/CALL-W1/classification"
        assert record.data == data

    def test_records_caller_state_write(self):
        writer = MockClassificationWriter()
        data = {"panic_level": "PANIC_HIGH", "caller_role": "VICTIM"}
        writer.write_caller_state("CALL-W2", data)

        assert len(writer.caller_state_writes) == 1
        record = writer.last_caller_state()
        assert record is not None
        assert record.call_id == "CALL-W2"
        assert record.path == "/calls/CALL-W2/caller_state"
        assert record.data == data

    def test_classifications_for_filters_by_call_id(self):
        writer = MockClassificationWriter()
        writer.write_classification("CALL-A", {"type": "FIRE"})
        writer.write_classification("CALL-B", {"type": "MEDICAL"})
        writer.write_classification("CALL-A", {"type": "CRIME"})

        a_writes = writer.classifications_for("CALL-A")
        assert len(a_writes) == 2
        b_writes = writer.classifications_for("CALL-B")
        assert len(b_writes) == 1

    def test_caller_states_for_filters_by_call_id(self):
        writer = MockClassificationWriter()
        writer.write_caller_state("CALL-X", {"panic_level": "CALM"})
        writer.write_caller_state("CALL-Y", {"panic_level": "PANIC_HIGH"})

        x_writes = writer.caller_states_for("CALL-X")
        assert len(x_writes) == 1
        y_writes = writer.caller_states_for("CALL-Y")
        assert len(y_writes) == 1


class TestFirebaseWriterPaths:
    """Firebase writer uses correct RTDB paths."""

    def test_classification_path_format(self):
        writer = MockClassificationWriter()
        writer.write_classification("CALL-P1", {})
        assert writer.last_classification().path == "/calls/CALL-P1/classification"

    def test_caller_state_path_format(self):
        writer = MockClassificationWriter()
        writer.write_caller_state("CALL-P2", {})
        assert writer.last_caller_state().path == "/calls/CALL-P2/caller_state"


# -----------------------------------------------------------------------
# Service-level integration tests
# -----------------------------------------------------------------------


class TestClassifyTranscriptService:
    """classify_transcript wires classifier → parser → writer correctly."""

    def test_returns_valid_emergency_classification(self):
        writer = MockClassificationWriter()
        configure(
            classifier=MockGeminiClassifier(
                emergency_type="FIRE",
                severity="HIGH",
                confidence=0.88,
            ),
            writer=writer,
        )

        result = classify_transcript("CALL-S1", "fire in the building")
        assert result.call_id == "CALL-S1"
        assert result.emergency_type == EmergencyType.FIRE
        assert result.severity == Severity.HIGH
        assert result.confidence == 0.88

    def test_writes_classification_to_firebase(self):
        writer = MockClassificationWriter()
        configure(classifier=MockGeminiClassifier(), writer=writer)

        classify_transcript("CALL-S2", "accident on highway")

        assert len(writer.classification_writes) == 1
        record = writer.last_classification()
        assert record.call_id == "CALL-S2"
        assert record.path == "/calls/CALL-S2/classification"

    def test_writes_caller_state_to_firebase(self):
        writer = MockClassificationWriter()
        configure(
            classifier=MockGeminiClassifier(
                panic_level="PANIC_HIGH",
                caller_role="VICTIM",
            ),
            writer=writer,
        )

        classify_transcript("CALL-S3", "help me please")

        assert len(writer.caller_state_writes) == 1
        record = writer.last_caller_state()
        assert record.call_id == "CALL-S3"
        assert record.path == "/calls/CALL-S3/caller_state"
        assert record.data["panic_level"] == "PANIC_HIGH"
        assert record.data["caller_role"] == "VICTIM"

    def test_classification_includes_model_version(self):
        configure(
            classifier=MockGeminiClassifier(model_version="gemini-1.5-pro-002"),
            writer=MockClassificationWriter(),
        )
        result = classify_transcript("CALL-S4", "test")
        assert result.model_version == "gemini-1.5-pro-002"

    def test_classification_includes_timestamp(self):
        configure(
            classifier=MockGeminiClassifier(),
            writer=MockClassificationWriter(),
        )
        result = classify_transcript("CALL-S5", "test")
        assert result.timestamp is not None


# -----------------------------------------------------------------------
# Parse classification tests
# -----------------------------------------------------------------------


class TestParseClassification:
    """_parse_classification converts raw JSON to EmergencyClassification."""

    def test_parses_complete_json(self):
        raw = {
            "emergency_type": "MEDICAL",
            "severity": "CRITICAL",
            "caller_state": {
                "panic_level": "PANIC_HIGH",
                "caller_role": "VICTIM",
            },
            "language_detected": "hi",
            "key_facts": ["chest pain", "elderly"],
            "confidence": 0.92,
        }
        result = _parse_classification("CALL-P1", raw, "gemini-1.5-pro")
        assert result.emergency_type == EmergencyType.MEDICAL
        assert result.severity == Severity.CRITICAL
        assert result.caller_state.panic_level == PanicLevel.PANIC_HIGH
        assert result.caller_state.caller_role == CallerRole.VICTIM
        assert result.language_detected == "hi"
        assert result.key_facts == ["chest pain", "elderly"]
        assert result.confidence == 0.92
        assert result.model_version == "gemini-1.5-pro"

    def test_applies_defaults_for_missing_fields(self):
        raw = {}
        result = _parse_classification("CALL-P2", raw, "test")
        assert result.emergency_type == EmergencyType.UNKNOWN
        assert result.severity == Severity.MODERATE
        assert result.caller_state.panic_level == PanicLevel.CALM
        assert result.caller_state.caller_role == CallerRole.BYSTANDER
        assert result.language_detected == "hi"
        assert result.key_facts == []
        assert result.confidence == 0.5


# -----------------------------------------------------------------------
# LiveGeminiClassifier placeholder test
# -----------------------------------------------------------------------


class TestLiveGeminiClassifier:
    """LiveGeminiClassifier raises NotImplementedError without API key."""

    def test_raises_not_implemented(self):
        classifier = LiveGeminiClassifier()
        with pytest.raises(NotImplementedError, match="google-generativeai"):
            classifier.classify("test", "CALL-LIVE")


# -----------------------------------------------------------------------
# FirebaseClassificationWriter placeholder test
# -----------------------------------------------------------------------


class TestFirebaseClassificationWriter:
    """FirebaseClassificationWriter raises NotImplementedError without firebase-admin."""

    def test_write_classification_raises_not_implemented(self):
        writer = FirebaseClassificationWriter()
        with pytest.raises(NotImplementedError, match="firebase-admin"):
            writer.write_classification("CALL-FW1", {})

    def test_write_caller_state_raises_not_implemented(self):
        writer = FirebaseClassificationWriter()
        with pytest.raises(NotImplementedError, match="firebase-admin"):
            writer.write_caller_state("CALL-FW2", {})
