"""Property-based test for geospatial and status unit filtering.

Feature: crisislink-emergency-ai-copilot, Property 6: Geospatial and Status Unit Filtering

Validates: Requirements 4.1

Uses Hypothesis to generate random sets of Response_Units with various
locations and statuses, and a random caller location; verify only units with
status "available" AND within 15km radius are returned.
"""

from __future__ import annotations

import time

from hypothesis import given, settings
from hypothesis import strategies as st

from dispatch.geospatial import DEFAULT_RADIUS_KM, filter_units, haversine_km
from shared.models import Location, ResponseUnit, UnitStatus, UnitType


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid latitude range [-90, 90] and longitude range [-180, 180].
# We use a slightly narrower band to avoid degenerate pole/antimeridian edge
# cases that don't affect the core property being tested.
latitude_strategy = st.floats(min_value=-85.0, max_value=85.0, allow_nan=False, allow_infinity=False)
longitude_strategy = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)

location_strategy = st.builds(Location, lat=latitude_strategy, lng=longitude_strategy)

unit_status_strategy = st.sampled_from(list(UnitStatus))
unit_type_strategy = st.sampled_from(list(UnitType))

# Generate a single ResponseUnit with random location and status.
response_unit_strategy = st.builds(
    ResponseUnit,
    unit_id=st.from_regex(r"UNIT_[A-Z0-9]{3,6}", fullmatch=True),
    type=unit_type_strategy,
    status=unit_status_strategy,
    location=location_strategy,
    hospital_or_station=st.just("Test Station"),
    capabilities=st.just([]),
    last_updated=st.just(int(time.time())),
)

# A list of 0–20 response units (enough to exercise the filter meaningfully).
unit_list_strategy = st.lists(response_unit_strategy, min_size=0, max_size=20).map(
    # Ensure unique unit_ids so the filter doesn't see duplicates.
    lambda units: _deduplicate_units(units)
)


def _deduplicate_units(units: list[ResponseUnit]) -> list[ResponseUnit]:
    """Assign unique unit_ids to avoid collisions from random generation."""
    seen: set[str] = set()
    result: list[ResponseUnit] = []
    for i, u in enumerate(units):
        uid = f"UNIT_{i:04d}"
        if uid not in seen:
            seen.add(uid)
            result.append(u.model_copy(update={"unit_id": uid}))
    return result


# ---------------------------------------------------------------------------
# Property 6: Geospatial and Status Unit Filtering
# ---------------------------------------------------------------------------


class TestGeospatialAndStatusUnitFiltering:
    """Property 6: Geospatial and Status Unit Filtering

    For any set of Response_Units in Firebase and any caller location, the
    Dispatch Engine's unit query SHALL return only units where (a) the unit's
    status is "available" AND (b) the unit's GPS location is within a 15km
    radius of the caller location. No unit outside 15km or with a non-available
    status SHALL appear in the results.

    **Validates: Requirements 4.1**
    """

    @given(units=unit_list_strategy, caller_location=location_strategy)
    @settings(max_examples=200)
    def test_only_available_units_within_radius_are_returned(
        self,
        units: list[ResponseUnit],
        caller_location: Location,
    ):
        """Every returned unit must be available AND within 15km of the caller.

        **Validates: Requirements 4.1**
        """
        now = time.time()
        results = filter_units(units, caller_location, radius_km=DEFAULT_RADIUS_KM, now_unix=now)

        for fu in results:
            # (a) Status must be "available"
            assert fu.unit.status == UnitStatus.AVAILABLE, (
                f"Unit {fu.unit.unit_id} has status '{fu.unit.status}' "
                f"but only 'available' units should be returned"
            )
            # (b) Distance must be within 15km
            dist = haversine_km(
                caller_location.lat,
                caller_location.lng,
                fu.unit.location.lat,
                fu.unit.location.lng,
            )
            assert dist <= DEFAULT_RADIUS_KM, (
                f"Unit {fu.unit.unit_id} is {dist:.2f} km away "
                f"but the radius limit is {DEFAULT_RADIUS_KM} km"
            )

    @given(units=unit_list_strategy, caller_location=location_strategy)
    @settings(max_examples=200)
    def test_no_non_available_unit_is_returned(
        self,
        units: list[ResponseUnit],
        caller_location: Location,
    ):
        """No unit with a non-available status should appear in the results.

        **Validates: Requirements 4.1**
        """
        now = time.time()
        results = filter_units(units, caller_location, radius_km=DEFAULT_RADIUS_KM, now_unix=now)
        returned_ids = {fu.unit.unit_id for fu in results}

        for unit in units:
            if unit.status != UnitStatus.AVAILABLE:
                assert unit.unit_id not in returned_ids, (
                    f"Unit {unit.unit_id} with status '{unit.status}' "
                    f"should NOT appear in filtered results"
                )

    @given(units=unit_list_strategy, caller_location=location_strategy)
    @settings(max_examples=200)
    def test_no_unit_outside_radius_is_returned(
        self,
        units: list[ResponseUnit],
        caller_location: Location,
    ):
        """No unit beyond 15km should appear in the results.

        **Validates: Requirements 4.1**
        """
        now = time.time()
        results = filter_units(units, caller_location, radius_km=DEFAULT_RADIUS_KM, now_unix=now)
        returned_ids = {fu.unit.unit_id for fu in results}

        for unit in units:
            dist = haversine_km(
                caller_location.lat,
                caller_location.lng,
                unit.location.lat,
                unit.location.lng,
            )
            if dist > DEFAULT_RADIUS_KM:
                assert unit.unit_id not in returned_ids, (
                    f"Unit {unit.unit_id} is {dist:.2f} km away (> {DEFAULT_RADIUS_KM} km) "
                    f"and should NOT appear in filtered results"
                )

    @given(units=unit_list_strategy, caller_location=location_strategy)
    @settings(max_examples=200)
    def test_all_eligible_units_are_returned(
        self,
        units: list[ResponseUnit],
        caller_location: Location,
    ):
        """Every unit that is available AND within 15km MUST be returned (completeness).

        **Validates: Requirements 4.1**
        """
        now = time.time()
        results = filter_units(units, caller_location, radius_km=DEFAULT_RADIUS_KM, now_unix=now)
        returned_ids = {fu.unit.unit_id for fu in results}

        for unit in units:
            if unit.status != UnitStatus.AVAILABLE:
                continue
            dist = haversine_km(
                caller_location.lat,
                caller_location.lng,
                unit.location.lat,
                unit.location.lng,
            )
            if dist <= DEFAULT_RADIUS_KM:
                assert unit.unit_id in returned_ids, (
                    f"Unit {unit.unit_id} is available and {dist:.2f} km away "
                    f"(<= {DEFAULT_RADIUS_KM} km) but was NOT returned"
                )
