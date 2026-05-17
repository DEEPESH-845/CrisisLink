"""Google Maps Routes API client protocol and mock implementation.

Provides a protocol for ETA calculation and a mock implementation for
testing and development.

Requirements: 4.2
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

import httpx

from shared.models import Location

from .geospatial import haversine_km

logger = logging.getLogger(__name__)

# Urban traffic parameters for straight-line fallback ETA.
# Road distance ≈ straight-line × tortuosity; city speed ≈ 25 km/h.
_FALLBACK_SPEED_KMH = 25.0
_FALLBACK_TORTUOSITY = 1.5
_FALLBACK_MIN_ETA_MINUTES = 4.0  # minimum dispatch + mobilisation overhead


class MapsClient(Protocol):
    """Protocol for traffic-aware ETA calculation."""

    async def get_eta_minutes(
        self, origin: Location, destination: Location
    ) -> float | None:
        """Return traffic-aware ETA in minutes, or *None* on failure."""
        ...


class MockMapsClient:
    """Mock Maps client that estimates ETA from straight-line distance.

    Uses urban-realistic parameters: 25 km/h city speed, 1.5× tortuosity
    factor, and a 4-minute minimum for dispatch overhead.
    """

    def __init__(self, speed_kmh: float = _FALLBACK_SPEED_KMH) -> None:
        self._speed_kmh = speed_kmh

    async def get_eta_minutes(
        self, origin: Location, destination: Location
    ) -> float | None:
        dist = haversine_km(origin.lat, origin.lng, destination.lat, destination.lng)
        if self._speed_kmh <= 0:
            return None
        road_km = dist * _FALLBACK_TORTUOSITY
        eta = (road_km / self._speed_kmh) * 60.0
        return max(eta, _FALLBACK_MIN_ETA_MINUTES)


def fallback_eta_minutes(distance_km: float) -> float:
    """Compute a realistic urban fallback ETA when the Maps API is unavailable.

    Applies a 1.5× road-tortuosity factor over straight-line distance,
    uses 25 km/h city speed, and enforces a 4-minute minimum for
    dispatch mobilisation overhead.
    """
    road_km = distance_km * _FALLBACK_TORTUOSITY
    eta = (road_km / _FALLBACK_SPEED_KMH) * 60.0
    return max(eta, _FALLBACK_MIN_ETA_MINUTES)


class GoogleRoutesMapsClient:
    """Google Maps Routes API implementation.

    Falls back gracefully when the API key has service restrictions or
    the Routes API is not enabled — returns None so the caller uses the
    urban straight-line estimate instead.
    """

    _warned_about_restriction: bool = False

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 5.0) -> None:
        self._api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self._timeout = timeout_seconds

    async def get_eta_minutes(
        self, origin: Location, destination: Location
    ) -> float | None:
        if not self._api_key:
            return None

        payload = {
            "origin": {"location": {"latLng": {"latitude": origin.lat, "longitude": origin.lng}}},
            "destination": {
                "location": {
                    "latLng": {"latitude": destination.lat, "longitude": destination.lng}
                }
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "computeAlternativeRoutes": False,
            "languageCode": "en-IN",
            "units": "METRIC",
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                json=payload,
                headers=headers,
            )

        if response.status_code == 403:
            if not GoogleRoutesMapsClient._warned_about_restriction:
                GoogleRoutesMapsClient._warned_about_restriction = True
                logger.warning(
                    "Google Maps Routes API returned 403. The API key may have service "
                    "restrictions blocking routes.googleapis.com. To fix: Google Cloud "
                    "Console → Credentials → API key → API restrictions → add Routes API. "
                    "Using urban straight-line ETA fallback in the meantime."
                )
            return None

        response.raise_for_status()
        data = response.json()

        routes = data.get("routes") or []
        if not routes:
            return None
        duration = routes[0].get("duration")
        if not isinstance(duration, str) or not duration.endswith("s"):
            return None
        return float(duration[:-1]) / 60.0
