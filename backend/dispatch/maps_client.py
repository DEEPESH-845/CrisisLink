"""Google Maps Routes API client protocol and mock implementation.

Provides a protocol for ETA calculation and a mock implementation for
testing and development.

Requirements: 4.2
"""

from __future__ import annotations

import logging
from typing import Protocol

from shared.models import Location

from .geospatial import haversine_km

logger = logging.getLogger(__name__)

# Assumed average speed in km/h for straight-line fallback ETA.
_FALLBACK_SPEED_KMH = 40.0


class MapsClient(Protocol):
    """Protocol for traffic-aware ETA calculation."""

    async def get_eta_minutes(
        self, origin: Location, destination: Location
    ) -> float | None:
        """Return traffic-aware ETA in minutes, or *None* on failure."""
        ...


class MockMapsClient:
    """Mock Maps client that estimates ETA from straight-line distance.

    Uses a configurable average speed (default 40 km/h) to convert
    Haversine distance into an estimated travel time.
    """

    def __init__(self, speed_kmh: float = _FALLBACK_SPEED_KMH) -> None:
        self._speed_kmh = speed_kmh

    async def get_eta_minutes(
        self, origin: Location, destination: Location
    ) -> float | None:
        dist = haversine_km(origin.lat, origin.lng, destination.lat, destination.lng)
        if self._speed_kmh <= 0:
            return None
        return (dist / self._speed_kmh) * 60.0


def fallback_eta_minutes(distance_km: float) -> float:
    """Compute a straight-line fallback ETA when the Maps API fails.

    Assumes an average speed of 40 km/h.
    """
    return (distance_km / _FALLBACK_SPEED_KMH) * 60.0
