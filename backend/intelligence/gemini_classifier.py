"""Gemini 1.5 Pro classifier protocol and implementations.

Defines a ``GeminiClassifier`` protocol for emergency classification,
a ``MockGeminiClassifier`` for testing, and a placeholder
``LiveGeminiClassifier`` for production use with the Gemini API.

The protocol/mock pattern mirrors the Whisper transcriber approach used
in the Speech Ingestion Service, allowing full pipeline testing without
live API calls.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 3.1, 3.2
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from shared.models import (
    CallerRole,
    CallerState,
    EmergencyClassification,
    EmergencyType,
    PanicLevel,
    Severity,
)

from .gemini_prompts import SYSTEM_PROMPT, build_classification_prompt

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Raw result from a Gemini classification call."""

    raw_json: dict[str, Any]
    latency_seconds: float
    model_version: str = "gemini-1.5-pro"


class GeminiAPIError(Exception):
    """Base exception for Gemini API errors."""


class GeminiTimeoutError(GeminiAPIError):
    """Raised when the Gemini API call exceeds the timeout threshold."""


class GeminiInvalidJSONError(GeminiAPIError):
    """Raised when Gemini returns a response that is not valid JSON."""


class GeminiQuotaExceededError(GeminiAPIError):
    """Raised when the Gemini API returns HTTP 429 (quota exceeded)."""


@runtime_checkable
class GeminiClassifier(Protocol):
    """Protocol for Gemini-based emergency classification."""

    def classify(self, transcript: str, call_id: str) -> ClassificationResult:
        """Classify an emergency call transcript.

        Parameters
        ----------
        transcript : str
            The rolling transcript text from the emergency call.
        call_id : str
            Unique call session identifier for logging and tracing.

        Returns
        -------
        ClassificationResult
            The raw classification JSON, latency, and model version.

        Raises
        ------
        GeminiTimeoutError
            If the API call exceeds the timeout threshold (5s).
        GeminiInvalidJSONError
            If the API returns a response that cannot be parsed as JSON.
        GeminiQuotaExceededError
            If the API returns HTTP 429.
        """
        ...


class MockGeminiClassifier:
    """Mock classifier for testing — returns configurable classifications.

    By default returns a valid MEDICAL/CRITICAL classification. Override
    via constructor parameters or by setting attributes directly.
    """

    def __init__(
        self,
        emergency_type: str = "MEDICAL",
        severity: str = "CRITICAL",
        panic_level: str = "PANIC_HIGH",
        caller_role: str = "VICTIM",
        language_detected: str = "hi",
        key_facts: list[str] | None = None,
        confidence: float = 0.92,
        latency: float = 1.5,
        model_version: str = "gemini-1.5-pro-mock",
        *,
        raise_timeout: bool = False,
        raise_invalid_json: bool = False,
        raise_quota_exceeded: bool = False,
    ) -> None:
        self.emergency_type = emergency_type
        self.severity = severity
        self.panic_level = panic_level
        self.caller_role = caller_role
        self.language_detected = language_detected
        self.key_facts = key_facts if key_facts is not None else ["chest pain", "elderly person"]
        self.confidence = confidence
        self.latency = latency
        self.model_version = model_version
        self.raise_timeout = raise_timeout
        self.raise_invalid_json = raise_invalid_json
        self.raise_quota_exceeded = raise_quota_exceeded
        self.call_count: int = 0
        self.last_transcript: str | None = None
        self.last_call_id: str | None = None

    def classify(self, transcript: str, call_id: str) -> ClassificationResult:
        """Return a configurable classification result.

        Raises the configured error if any ``raise_*`` flag is set.
        """
        self.call_count += 1
        self.last_transcript = transcript
        self.last_call_id = call_id

        if self.raise_timeout:
            raise GeminiTimeoutError(
                f"Gemini API timeout after 5s for call {call_id}"
            )
        if self.raise_invalid_json:
            raise GeminiInvalidJSONError(
                f"Gemini returned invalid JSON for call {call_id}"
            )
        if self.raise_quota_exceeded:
            raise GeminiQuotaExceededError(
                f"Gemini API quota exceeded (HTTP 429) for call {call_id}"
            )

        raw_json = {
            "emergency_type": self.emergency_type,
            "severity": self.severity,
            "caller_state": {
                "panic_level": self.panic_level,
                "caller_role": self.caller_role,
            },
            "language_detected": self.language_detected,
            "key_facts": self.key_facts,
            "confidence": self.confidence,
        }

        return ClassificationResult(
            raw_json=raw_json,
            latency_seconds=self.latency,
            model_version=self.model_version,
        )


class LiveGeminiClassifier:
    """Production Gemini 1.5 Pro classifier.

    This is a placeholder that documents the expected integration points.
    The real implementation requires the ``google-generativeai`` package
    and a valid API key.

    The production flow:
    1. Build the system prompt and classification prompt.
    2. Call Gemini 1.5 Pro with streaming enabled.
    3. Accumulate streamed tokens into a complete JSON response.
    4. Parse and validate the JSON against the Emergency_Classification schema.
    5. Return the ClassificationResult with measured latency.

    Error handling:
    - Timeout (> 5s): raise GeminiTimeoutError
    - Invalid JSON: raise GeminiInvalidJSONError
    - HTTP 429: raise GeminiQuotaExceededError
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        timeout_seconds: float = 5.0,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    def classify(self, transcript: str, call_id: str) -> ClassificationResult:
        """Classify using Gemini 1.5 Pro.

        Raises ``NotImplementedError`` until the google-generativeai
        package is configured with a valid API key.
        """
        _ = build_classification_prompt(transcript)
        _ = SYSTEM_PROMPT
        raise NotImplementedError(
            f"LiveGeminiClassifier({self._model_name!r}) requires "
            "google-generativeai with a valid API key. "
            "Use MockGeminiClassifier for testing."
        )
