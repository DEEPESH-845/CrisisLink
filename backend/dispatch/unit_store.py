"""Unit store protocol and mock implementation for querying Response_Units.

In production this reads from Firebase RTDB ``/units/``.  The mock
implementation allows tests to run without a live Firebase connection.

Requirements: 4.1, 8.3
"""

from __future__ import annotations

from typing import Protocol

from shared.models import ResponseUnit


class UnitStore(Protocol):
    """Protocol for querying response units from the data store."""

    async def get_all_units(self) -> list[ResponseUnit]:
        """Return all known response units regardless of status."""
        ...

    async def update_unit_status(self, unit_id: str, status: str) -> None:
        """Update a unit's status in the data store."""
        ...


class MockUnitStore:
    """In-memory unit store for testing and development."""

    def __init__(self, units: list[ResponseUnit] | None = None) -> None:
        self._units: dict[str, ResponseUnit] = {}
        if units:
            for u in units:
                self._units[u.unit_id] = u

    async def get_all_units(self) -> list[ResponseUnit]:
        return list(self._units.values())

    async def update_unit_status(self, unit_id: str, status: str) -> None:
        if unit_id in self._units:
            self._units[unit_id] = self._units[unit_id].model_copy(
                update={"status": status}
            )

    def add_unit(self, unit: ResponseUnit) -> None:
        """Helper for tests to add units."""
        self._units[unit.unit_id] = unit

    def get_unit(self, unit_id: str) -> ResponseUnit | None:
        """Helper for tests to inspect a unit."""
        return self._units.get(unit_id)
