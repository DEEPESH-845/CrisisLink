"""Composite score ranking and Dispatch_Card generation.

Implements the ranking formula:
    composite_score = (0.6 × ETA_normalized) + (0.4 × capability_match)

Lower composite score = better (closer + more capable).

Requirements: 4.3, 4.4, 4.6
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from shared.models import (
    DispatchCard,
    DispatchRecommendation,
    EmergencyClassification,
)

# Weights for the composite score formula.
ETA_WEIGHT = 0.6
CAPABILITY_WEIGHT = 0.4

# Maximum number of recommendations in a Dispatch_Card.
MAX_RECOMMENDATIONS = 3


@dataclass
class ScoredUnit:
    """Intermediate representation of a unit with ETA and capability data."""

    unit_id: str
    unit_type: str
    hospital_or_station: str
    eta_minutes: float
    capability_match: float
    distance_km: float


def _compute_capability_match(
    unit_capabilities: list[str],
    classification: EmergencyClassification,
) -> float:
    """Compute a capability match score in [0.0, 1.0].

    The score is based on how well the unit's capability tags match the
    emergency type and key facts.  A simple keyword overlap approach is
    used here; production would use a more sophisticated matching model.
    """
    if not unit_capabilities:
        return 0.0

    # Build a set of desired capabilities from the classification.
    desired: set[str] = set()

    etype = classification.emergency_type.value.lower()
    # Map emergency types to relevant capability keywords.
    _type_capabilities: dict[str, list[str]] = {
        "medical": ["cardiac", "trauma", "pediatric", "als", "bls"],
        "fire": ["hazmat", "fire", "rescue", "ladder"],
        "crime": ["armed", "tactical", "patrol"],
        "accident": ["trauma", "extrication", "rescue"],
        "disaster": ["hazmat", "rescue", "search"],
    }
    desired.update(_type_capabilities.get(etype, []))

    # Also consider key_facts for more specific matching.
    key_facts_lower = " ".join(classification.key_facts).lower()
    if "cardiac" in key_facts_lower or "heart" in key_facts_lower:
        desired.add("cardiac")
    if "pediatric" in key_facts_lower or "child" in key_facts_lower:
        desired.add("pediatric")
    if "trauma" in key_facts_lower:
        desired.add("trauma")

    if not desired:
        return 0.5  # Neutral score when no specific capabilities needed.

    unit_caps_lower = {c.lower() for c in unit_capabilities}
    matches = len(desired & unit_caps_lower)
    return matches / len(desired)


def normalize_etas(etas: list[float]) -> list[float]:
    """Min-max normalize a list of ETA values to [0, 1].

    If all ETAs are equal, returns 0.0 for each (all equally close).
    """
    if not etas:
        return []

    min_eta = min(etas)
    max_eta = max(etas)
    spread = max_eta - min_eta

    if spread == 0:
        return [0.0] * len(etas)

    return [(eta - min_eta) / spread for eta in etas]


def compute_composite_scores(
    units: list[ScoredUnit],
) -> list[tuple[ScoredUnit, float]]:
    """Compute composite scores for a list of scored units.

    Returns (unit, composite_score) pairs sorted ascending by score.
    """
    if not units:
        return []

    etas = [u.eta_minutes for u in units]
    normalized = normalize_etas(etas)

    scored: list[tuple[ScoredUnit, float]] = []
    for unit, eta_norm in zip(units, normalized):
        # Lower capability_match is better for the composite (inverted).
        # Actually per design: lower composite = better.
        # ETA_normalized: lower is better (closer).
        # capability_match: higher is better (more capable), so we invert.
        composite = (ETA_WEIGHT * eta_norm) + (CAPABILITY_WEIGHT * (1.0 - unit.capability_match))
        scored.append((unit, composite))

    scored.sort(key=lambda pair: pair[1])
    return scored


def build_dispatch_card(
    call_id: str,
    scored_units: list[tuple[ScoredUnit, float]],
    classification: EmergencyClassification,
) -> DispatchCard:
    """Build a Dispatch_Card from scored units.

    Takes the top 3 (or fewer) units and creates the card.

    Requirements: 4.4, 4.6
    """
    top = scored_units[:MAX_RECOMMENDATIONS]

    recommendations = [
        DispatchRecommendation(
            unit_id=unit.unit_id,
            unit_type=unit.unit_type,
            hospital_or_station=unit.hospital_or_station,
            eta_minutes=round(unit.eta_minutes, 2),
            capability_match=round(unit.capability_match, 4),
            composite_score=round(score, 4),
            distance_km=round(unit.distance_km, 2),
        )
        for unit, score in top
    ]

    return DispatchCard(
        call_id=call_id,
        recommendations=recommendations,
        generated_at=datetime.now(timezone.utc),
        classification_ref=f"{classification.call_id}/{classification.timestamp.isoformat()}",
    )


def rank_and_build_card(
    call_id: str,
    scored_units: list[ScoredUnit],
    classification: EmergencyClassification,
) -> DispatchCard:
    """Convenience function: compute scores, rank, and build the card."""
    scored = compute_composite_scores(scored_units)
    return build_dispatch_card(call_id, scored, classification)
