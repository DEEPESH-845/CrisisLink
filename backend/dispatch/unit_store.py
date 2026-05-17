"""Unit store protocol and mock implementation for querying Response_Units.

In production this reads from Firebase RTDB ``/units/``.  The mock
implementation allows tests to run without a live Firebase connection.

Requirements: 4.1, 8.3
"""

from __future__ import annotations

from typing import Protocol

from shared.models import ResponseUnit
from shared.firebase.paths import all_units, unit


class UnitStore(Protocol):
    """Protocol for querying response units from the data store."""

    async def get_all_units(self) -> list[ResponseUnit]:
        """Return all known response units regardless of status."""
        ...

    async def update_unit_status(self, unit_id: str, status: str) -> None:
        """Update a unit's status in the data store."""
        ...

    async def set_unit_dispatch(self, unit_id: str, dispatch_data: dict) -> None:
        """Attach the active dispatch assignment to a unit."""
        ...


class MockUnitStore:
    """In-memory unit store for testing and development."""

    def __init__(self, units: list[ResponseUnit] | None = None) -> None:
        self._units: dict[str, ResponseUnit] = {}
        self._dispatches: dict[str, dict] = {}
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

    async def set_unit_dispatch(self, unit_id: str, dispatch_data: dict) -> None:
        self._dispatches[unit_id] = dispatch_data

    def add_unit(self, unit: ResponseUnit) -> None:
        """Helper for tests to add units."""
        self._units[unit.unit_id] = unit

    def get_unit(self, unit_id: str) -> ResponseUnit | None:
        """Helper for tests to inspect a unit."""
        return self._units.get(unit_id)

    def get_dispatch(self, unit_id: str) -> dict | None:
        """Helper for tests to inspect dispatch assignment data."""
        return self._dispatches.get(unit_id)


class FirebaseUnitStore:
    """Firebase RTDB-backed unit store.

    Uses Application Default Credentials or an already-initialised
    ``firebase_admin`` app. It preserves the mock store API so dispatch logic
    can swap implementations without code changes.
    """

    async def get_all_units(self) -> list[ResponseUnit]:
        ref = self._db().reference(all_units())
        data = ref.get() or {}
        units: list[ResponseUnit] = []
        for unit_id, raw in data.items():
            if not isinstance(raw, dict):
                continue
            payload = dict(raw)
            payload.setdefault("unit_id", unit_id)
            try:
                units.append(ResponseUnit.model_validate(payload))
            except Exception:
                continue
        return units

    async def update_unit_status(self, unit_id: str, status: str) -> None:
        self._db().reference(unit(unit_id)).update({"status": status})

    async def set_unit_dispatch(self, unit_id: str, dispatch_data: dict) -> None:
        self._db().reference(f"{unit(unit_id)}/dispatch").set(dispatch_data)

    @staticmethod
    def _db():
        try:
            import firebase_admin
            from firebase_admin import credentials, db

            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.ApplicationDefault())
            return db
        except Exception as exc:
            raise NotImplementedError("firebase-admin is not configured for UnitStore") from exc
