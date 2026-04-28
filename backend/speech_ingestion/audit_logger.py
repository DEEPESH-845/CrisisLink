"""Audit logging protocol and implementations for the Speech Ingestion Service.

Defines an ``AuditLogger`` protocol for recording failover events and other
audit-worthy actions to BigQuery.  Includes a ``MockAuditLogger`` for testing
and a placeholder ``BigQueryAuditLogger`` for production.

Requirements: 1.6
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@dataclass
class AuditEntry:
    """A single audit log entry for failover or other events."""

    call_id: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AuditLogger(Protocol):
    """Protocol for writing audit log entries."""

    def log(self, entry: AuditEntry) -> None:
        """Persist an audit log entry.

        Parameters
        ----------
        entry : AuditEntry
            The audit event to record.
        """
        ...


class MockAuditLogger:
    """In-memory mock audit logger for testing — records all entries."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        """Record the entry for later assertion in tests."""
        self.entries.append(entry)

    def last_entry(self) -> AuditEntry | None:
        """Return the most recent entry, or ``None``."""
        return self.entries[-1] if self.entries else None

    def entries_for(self, call_id: str) -> list[AuditEntry]:
        """Return all entries for a specific *call_id*."""
        return [e for e in self.entries if e.call_id == call_id]


class BigQueryAuditLogger:
    """Production audit logger that writes entries to BigQuery.

    Requires ``google-cloud-bigquery`` client to be initialised.  This is
    a placeholder — the real implementation calls
    ``client.insert_rows_json(table, [row])``.
    """

    def __init__(self, project_id: str = "", dataset: str = "crisislink", table: str = "audit_log") -> None:
        self._project_id = project_id
        self._dataset = dataset
        self._table = table

    def log(self, entry: AuditEntry) -> None:
        """Write the audit entry to BigQuery.

        Raises ``NotImplementedError`` until the BigQuery client is
        initialised in the deployment environment.
        """
        raise NotImplementedError(
            f"BigQueryAuditLogger requires google-cloud-bigquery initialisation. "
            f"Would write to {self._project_id}.{self._dataset}.{self._table}. "
            f"Use MockAuditLogger for testing."
        )
