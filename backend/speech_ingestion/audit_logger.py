"""Audit logging protocol and implementations for the Speech Ingestion Service.

Defines an ``AuditLogger`` protocol for recording failover events and other
audit-worthy actions to BigQuery.  Includes a ``MockAuditLogger`` for testing
and a placeholder ``BigQueryAuditLogger`` for production.

Requirements: 1.6
"""

from __future__ import annotations

import json
import os
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

    Requires Application Default Credentials or ``GOOGLE_APPLICATION_CREDENTIALS``.
    The destination table defaults to
    ``{GCP_PROJECT_ID}.crisislink.audit_log`` and can be overridden by
    constructor arguments.
    """

    def __init__(self, project_id: str = "", dataset: str = "crisislink", table: str = "audit_log") -> None:
        self._project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self._dataset = dataset
        self._table = table
        self._client = None

    def log(self, entry: AuditEntry) -> None:
        """Write the audit entry to BigQuery."""
        if not self._project_id:
            raise NotImplementedError(
                "BigQueryAuditLogger requires GCP_PROJECT_ID or an explicit project_id"
            )

        if self._client is None:
            from google.cloud import bigquery  # type: ignore[import-untyped]

            self._client = bigquery.Client(project=self._project_id)

        table_id = f"{self._project_id}.{self._dataset}.{self._table}"
        row = {
            "call_id": entry.call_id,
            "event_type": entry.event_type,
            "timestamp": entry.timestamp.isoformat(),
            "payload_json": json.dumps(entry.payload, ensure_ascii=False),
        }
        errors = self._client.insert_rows_json(table_id, [row])
        if errors:
            raise RuntimeError(f"BigQuery audit insert failed: {errors}")
