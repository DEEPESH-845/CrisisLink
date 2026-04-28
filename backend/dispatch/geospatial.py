"""Geospatial utilities for the Dispatch Service.

Provides Haversine distance calculation and unit filtering by radius
and availability status.

Requirements: 4.1, 4.2, 8.3
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from shared.models import Location, ResponseUnit, UnitStatus

# Default search radius in kilometres.
DEFAULT_RADIUS_KM = 15.0
EXPANDED_RADIUS_KM = 30.0

# A unit's location is considered stale if its last_updated timestamp
# is older than this many seconds.
STALE_THRESHOLD_SECONDS = 60

# Earth's mean radius in kilometres (WGS-84 approximation).
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in km between two points.

    Uses the Haversine formula with Earth radius = 6371 km.
    """
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_KM * c


@dataclass
class FilteredUnit:
    """A Response_Unit that passed geospatial and status filtering."""

    unit: ResponseUnit
    distance_km: float
    location_stale: bool


def filter_units(
    units: list[ResponseUnit],
    caller_location: Location,
    radius_km: float = DEFAULT_RADIUS_KM,
    now_unix: float | None = None,
) -> list[FilteredUnit]:
    """Return units that are available and within *radius_km* of the caller.

    Parameters
    ----------
    units:
        All known response units (any status).
    caller_location:
        The caller's GPS coordinates.
    radius_km:
        Maximum straight-line distance to include a unit.
    now_unix:
        Current Unix timestamp.  Defaults to ``time.time()`` when *None*.

    Returns
    -------
    list[FilteredUnit]
        Units with status ``available`` within the given radius, annotated
        with distance and staleness flag.
    """
    if now_unix is None:
        now_unix = time.time()

    results: list[FilteredUnit] = []
    for unit in units:
        if unit.status != UnitStatus.AVAILABLE:
            continue

        dist = haversine_km(
            caller_location.lat,
            caller_location.lng,
            unit.location.lat,
            unit.location.lng,
        )
        if dist > radius_km:
            continue

        stale = (now_unix - unit.last_updated) > STALE_THRESHOLD_SECONDS
        results.append(FilteredUnit(unit=unit, distance_km=dist, location_stale=stale))

    return results


def filter_units_with_expansion(
    units: list[ResponseUnit],
    caller_location: Location,
    now_unix: float | None = None,
) -> list[FilteredUnit]:
    """Filter units within 15 km, expanding to 30 km if none found.

    Requirements: 4.1 — expand search to 30 km when no units within 15 km.
    """
    results = filter_units(
        units, caller_location, radius_km=DEFAULT_RADIUS_KM, now_unix=now_unix
    )
    if not results:
        results = filter_units(
            units, caller_location, radius_km=EXPANDED_RADIUS_KM, now_unix=now_unix
        )
    return results
