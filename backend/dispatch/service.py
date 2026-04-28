"""Main dispatch service logic.

Orchestrates the full dispatch recommendation pipeline:
1. Query available units from the unit store
2. Filter by geospatial proximity and availability
3. Calculate ETAs via Maps API (with fallback)
4. Compute capability match scores
5. Rank by composite score and build Dispatch_Card
6. Write Dispatch_Card to Firebase RTDB

Requirements: 4.1, 4.2, 4.3, 4.4, 4.6
"""

from __future__ import annotations

import logging

from shared.models import (
    DispatchCard,
    EmergencyClassification,
    Location,
)

from .geospatial import FilteredUnit, filter_units_with_expansion
from .maps_client import MapsClient, fallback_eta_minutes
from .ranking import ScoredUnit, _compute_capability_match, rank_and_build_card
from .unit_store import UnitStore

logger = logging.getLogger(__name__)


async def _get_eta_for_unit(
    maps_client: MapsClient,
    unit_location: Location,
    caller_location: Location,
    fallback_distance_km: float,
) -> float:
    """Get traffic-aware ETA, falling back to straight-line estimate."""
    try:
        eta = await maps_client.get_eta_minutes(unit_location, caller_location)
        if eta is not None:
            return eta
    except Exception:
        logger.warning("Maps API call failed, using fallback ETA")

    return fallback_eta_minutes(fallback_distance_km)


async def generate_recommendations(
    call_id: str,
    classification: EmergencyClassification,
    caller_location: Location,
    unit_store: UnitStore,
    maps_client: MapsClient,
) -> DispatchCard:
    """Run the full dispatch recommendation pipeline.

    Returns a DispatchCard with ranked recommendations.
    """
    # 1. Get all units from the store
    all_units = await unit_store.get_all_units()

    # 2. Filter by availability and proximity (with 15→30 km expansion)
    filtered: list[FilteredUnit] = filter_units_with_expansion(
        all_units, caller_location
    )

    if not filtered:
        logger.warning("No available units found for call %s", call_id)
        return DispatchCard(
            call_id=call_id,
            recommendations=[],
            generated_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
            classification_ref=f"{classification.call_id}/{classification.timestamp.isoformat()}",
        )

    # 3. Calculate ETAs and capability scores
    scored_units: list[ScoredUnit] = []
    for fu in filtered:
        eta = await _get_eta_for_unit(
            maps_client,
            fu.unit.location,
            caller_location,
            fu.distance_km,
        )

        cap_match = _compute_capability_match(
            fu.unit.capabilities, classification
        )

        scored_units.append(
            ScoredUnit(
                unit_id=fu.unit.unit_id,
                unit_type=fu.unit.type.value,
                hospital_or_station=fu.unit.hospital_or_station,
                eta_minutes=eta,
                capability_match=cap_match,
                distance_km=fu.distance_km,
            )
        )

    # 4. Rank and build the Dispatch_Card
    card = rank_and_build_card(call_id, scored_units, classification)

    logger.info(
        "Generated dispatch card for call %s with %d recommendations",
        call_id,
        len(card.recommendations),
    )
    return card
