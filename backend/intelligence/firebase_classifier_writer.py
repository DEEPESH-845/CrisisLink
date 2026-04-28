"""Firebase Realtime Database writer for classification results.

Defines a ``ClassificationWriter`` protocol and implementations for
writing Emergency_Classification and CallerState data to Firebase RTDB
at ``/calls/{call_id}/classification`` and ``/calls/{call_id}/caller_state``.

Mirrors the ``TranscriptWriter`` pattern from the Speech Ingestion Service.

Requirements: 2.5, 2.7, 3.1, 3.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from shared.firebase.paths import call_caller_state, call_classification


@runtime_checkable
class ClassificationWriter(Protocol):
    """Protocol for writing classification results to a persistent store."""

    def write_classification(
        self,
        call_id: str,
        classification_data: dict[str, Any],
    ) -> None:
        """Write or update the Emergency_Classification for *call_id*.

        Parameters
        ----------
        call_id : str
            Unique call session identifier.
        classification_data : dict
            The full Emergency_Classification as a JSON-serialisable dict.
        """
        ...

    def write_caller_state(
        self,
        call_id: str,
        caller_state_data: dict[str, Any],
    ) -> None:
        """Write or update the CallerState for *call_id*.

        Parameters
        ----------
        call_id : str
            Unique call session identifier.
        caller_state_data : dict
            The CallerState as a JSON-serialisable dict
            (panic_level, caller_role).
        """
        ...


class MockClassificationWriter:
    """In-memory mock writer for testing — records all writes."""

    @dataclass
    class WriteRecord:
        """A single recorded write operation."""

        call_id: str
        path: str
        data: dict[str, Any]

    def __init__(self) -> None:
        self.classification_writes: list[MockClassificationWriter.WriteRecord] = []
        self.caller_state_writes: list[MockClassificationWriter.WriteRecord] = []

    def write_classification(
        self,
        call_id: str,
        classification_data: dict[str, Any],
    ) -> None:
        """Record the classification write for later assertion in tests."""
        path = call_classification(call_id)
        self.classification_writes.append(
            self.WriteRecord(
                call_id=call_id,
                path=path,
                data=classification_data,
            )
        )

    def write_caller_state(
        self,
        call_id: str,
        caller_state_data: dict[str, Any],
    ) -> None:
        """Record the caller state write for later assertion in tests."""
        path = call_caller_state(call_id)
        self.caller_state_writes.append(
            self.WriteRecord(
                call_id=call_id,
                path=path,
                data=caller_state_data,
            )
        )

    def last_classification(self) -> WriteRecord | None:
        """Return the most recent classification write, or ``None``."""
        return self.classification_writes[-1] if self.classification_writes else None

    def last_caller_state(self) -> WriteRecord | None:
        """Return the most recent caller state write, or ``None``."""
        return self.caller_state_writes[-1] if self.caller_state_writes else None

    def classifications_for(self, call_id: str) -> list[WriteRecord]:
        """Return all classification writes for a specific *call_id*."""
        return [w for w in self.classification_writes if w.call_id == call_id]

    def caller_states_for(self, call_id: str) -> list[WriteRecord]:
        """Return all caller state writes for a specific *call_id*."""
        return [w for w in self.caller_state_writes if w.call_id == call_id]


class FirebaseClassificationWriter:
    """Production writer that pushes classifications to Firebase RTDB.

    Requires ``firebase_admin`` to be initialised before use. This is a
    placeholder — the real implementation calls
    ``db.reference(path).set(payload)``.
    """

    def write_classification(
        self,
        call_id: str,
        classification_data: dict[str, Any],
    ) -> None:
        """Write the classification payload to Firebase RTDB.

        Raises ``NotImplementedError`` until firebase-admin is initialised
        in the deployment environment.
        """
        path = call_classification(call_id)
        raise NotImplementedError(
            f"FirebaseClassificationWriter requires firebase-admin initialisation. "
            f"Would write to {path}. Use MockClassificationWriter for testing."
        )

    def write_caller_state(
        self,
        call_id: str,
        caller_state_data: dict[str, Any],
    ) -> None:
        """Write the caller state payload to Firebase RTDB.

        Raises ``NotImplementedError`` until firebase-admin is initialised
        in the deployment environment.
        """
        path = call_caller_state(call_id)
        raise NotImplementedError(
            f"FirebaseClassificationWriter requires firebase-admin initialisation. "
            f"Would write to {path}. Use MockClassificationWriter for testing."
        )
