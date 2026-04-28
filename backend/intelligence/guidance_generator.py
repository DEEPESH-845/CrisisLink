"""Guidance Generator with caller state adaptation.

Selects the appropriate guidance register based on (panic_level, caller_role)
pairs and the appropriate protocol based on (emergency_type, key_facts).
Generates guidance text adapted to the caller's state and language.

Guidance is only generated for severity CRITICAL or HIGH (Requirement 5.1).

Register selection (Property 5 / Requirements 3.4, 3.5, 3.6):
- PANIC_HIGH + VICTIM → ultra-simple reassurance-first
- PANIC_HIGH + BYSTANDER → directive numbered steps
- CALM + BYSTANDER → full clinical protocol
- All other combinations → defined default register

Protocol selection (Property 9 / Requirements 5.6, 5.7):
- MEDICAL + cardiac indicators → CPR per Indian Resuscitation Council 2022
- FIRE → NDMA fire evacuation
- Other types → general guidance protocol

Requirements: 3.3, 3.4, 3.5, 3.6, 5.1, 5.2, 5.4, 5.5, 5.6, 5.7
"""

from __future__ import annotations

import logging
from enum import Enum

from shared.models import (
    CallerRole,
    CallerState,
    EmergencyClassification,
    EmergencyType,
    PanicLevel,
    Severity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GuidanceRegister(str, Enum):
    """Communication register for caller guidance.

    Determines the tone, complexity, and structure of guidance text
    based on the caller's panic level and role.
    """

    REASSURANCE_FIRST = "REASSURANCE_FIRST"
    """Ultra-simple short sentences with reassurance-first language."""

    DIRECTIVE_STEPS = "DIRECTIVE_STEPS"
    """Directive numbered steps without medical jargon."""

    CLINICAL_PROTOCOL = "CLINICAL_PROTOCOL"
    """Full clinical protocol guidance."""

    DEFAULT = "DEFAULT"
    """Default register for all other (panic_level, caller_role) combinations."""


class GuidanceProtocol(str, Enum):
    """Emergency protocol for guidance content.

    Determines which published protocol to follow for the guidance text.
    """

    CPR_IRC_2022 = "CPR_IRC_2022"
    """CPR guidance per Indian Resuscitation Council 2022 protocols."""

    FIRE_NDMA = "FIRE_NDMA"
    """Fire evacuation guidance per NDMA India protocols."""

    GENERAL = "GENERAL"
    """General guidance protocol for all other emergency types."""


# ---------------------------------------------------------------------------
# Cardiac indicator keywords
# ---------------------------------------------------------------------------

CARDIAC_INDICATORS = frozenset({
    "cardiac",
    "heart attack",
    "chest pain",
    "cardiac arrest",
    "cpr",
})


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def select_guidance_register(
    panic_level: PanicLevel,
    caller_role: CallerRole,
) -> GuidanceRegister:
    """Select the guidance register based on (panic_level, caller_role).

    Mapping (Property 5):
    - PANIC_HIGH + VICTIM → REASSURANCE_FIRST
    - PANIC_HIGH + BYSTANDER → DIRECTIVE_STEPS
    - CALM + BYSTANDER → CLINICAL_PROTOCOL
    - All other combinations → DEFAULT

    Parameters
    ----------
    panic_level : PanicLevel
        The caller's detected panic level.
    caller_role : CallerRole
        The caller's detected role.

    Returns
    -------
    GuidanceRegister
        The selected guidance register.
    """
    if panic_level == PanicLevel.PANIC_HIGH and caller_role == CallerRole.VICTIM:
        return GuidanceRegister.REASSURANCE_FIRST
    if panic_level == PanicLevel.PANIC_HIGH and caller_role == CallerRole.BYSTANDER:
        return GuidanceRegister.DIRECTIVE_STEPS
    if panic_level == PanicLevel.CALM and caller_role == CallerRole.BYSTANDER:
        return GuidanceRegister.CLINICAL_PROTOCOL
    return GuidanceRegister.DEFAULT


def select_guidance_protocol(
    emergency_type: EmergencyType,
    key_facts: list[str],
) -> GuidanceProtocol:
    """Select the guidance protocol based on emergency type and key facts.

    Mapping (Property 9):
    - MEDICAL + cardiac indicators in key_facts → CPR_IRC_2022
    - FIRE → FIRE_NDMA
    - All other types → GENERAL

    Cardiac indicators are matched case-insensitively against each
    key fact string. A match on any indicator in any fact triggers
    the CPR protocol.

    Parameters
    ----------
    emergency_type : EmergencyType
        The classified emergency type.
    key_facts : list[str]
        Extracted facts from the transcript.

    Returns
    -------
    GuidanceProtocol
        The selected guidance protocol.
    """
    if emergency_type == EmergencyType.MEDICAL:
        for fact in key_facts:
            fact_lower = fact.lower()
            for indicator in CARDIAC_INDICATORS:
                if indicator in fact_lower:
                    return GuidanceProtocol.CPR_IRC_2022
        return GuidanceProtocol.GENERAL

    if emergency_type == EmergencyType.FIRE:
        return GuidanceProtocol.FIRE_NDMA

    return GuidanceProtocol.GENERAL


def should_generate_guidance(severity: Severity) -> bool:
    """Return True only for CRITICAL or HIGH severity.

    Property 8 / Requirement 5.1: Guidance is only generated when
    severity is CRITICAL or HIGH.

    Parameters
    ----------
    severity : Severity
        The classified severity level.

    Returns
    -------
    bool
        True if guidance should be generated.
    """
    return severity in (Severity.CRITICAL, Severity.HIGH)


def _build_register_prefix(register: GuidanceRegister) -> str:
    """Build the opening text segment based on the guidance register."""
    if register == GuidanceRegister.REASSURANCE_FIRST:
        return (
            "You are safe. Help is coming. "
            "Stay calm. Listen carefully."
        )
    if register == GuidanceRegister.DIRECTIVE_STEPS:
        return (
            "Follow these steps exactly:"
        )
    if register == GuidanceRegister.CLINICAL_PROTOCOL:
        return (
            "Clinical protocol guidance:"
        )
    # DEFAULT
    return (
        "Emergency guidance:"
    )


def _build_protocol_body(protocol: GuidanceProtocol) -> str:
    """Build the protocol-specific guidance body text."""
    if protocol == GuidanceProtocol.CPR_IRC_2022:
        return (
            "CPR Protocol (Indian Resuscitation Council 2022): "
            "1. Check responsiveness — tap shoulders and shout. "
            "2. Call for help and ask someone to bring an AED. "
            "3. Place heel of one hand on centre of chest. "
            "4. Push hard and fast — 5 cm depth, 100-120 per minute. "
            "5. Give 30 compressions then 2 rescue breaths. "
            "6. Continue until help arrives."
        )
    if protocol == GuidanceProtocol.FIRE_NDMA:
        return (
            "Fire Evacuation Protocol (NDMA India): "
            "1. Alert everyone nearby — shout fire. "
            "2. Do not use lifts — use stairs only. "
            "3. Stay low to avoid smoke — crawl if needed. "
            "4. Cover nose and mouth with wet cloth. "
            "5. Move to the nearest safe exit. "
            "6. Assemble at a safe distance from the building. "
            "7. Do not re-enter the building."
        )
    # GENERAL
    return (
        "General Emergency Guidance: "
        "1. Stay calm and assess the situation. "
        "2. Ensure your own safety first. "
        "3. Help is on the way — stay on the line. "
        "4. Follow operator instructions."
    )


def generate_guidance_text(
    classification: EmergencyClassification,
    caller_state: CallerState,
) -> str:
    """Generate guidance text based on classification and caller state.

    Combines the register (communication style) with the protocol
    (content) to produce adaptive guidance. Guidance is only generated
    for severity CRITICAL or HIGH (Requirement 5.1).

    The guidance text is generated in the native script of the detected
    language (Requirement 5.5). In this implementation, the text is
    produced in English as a base; production deployment will use
    Gemini 1.5 Pro to generate native-script text.

    Parameters
    ----------
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
        return ""

    register = select_guidance_register(
        caller_state.panic_level,
        caller_state.caller_role,
    )
    protocol = select_guidance_protocol(
        classification.emergency_type,
        classification.key_facts,
    )

    prefix = _build_register_prefix(register)
    body = _build_protocol_body(protocol)

    language_note = (
        f"[Language: {classification.language_detected}] "
    )

    guidance = f"{language_note}{prefix} {body}"

    logger.info(
        "Generated guidance for call %s: register=%s, protocol=%s, language=%s",
        classification.call_id,
        register.value,
        protocol.value,
        classification.language_detected,
    )

    return guidance
