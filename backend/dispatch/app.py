"""FastAPI application for the CrisisLink Dispatch Service.

Endpoints
---------
POST /api/v1/calls/{call_id}/dispatch/recommend
    Accept an Emergency_Classification and caller_location, return ranked
    Dispatch_Recommendations as a Dispatch_Card.

POST /api/v1/calls/{call_id}/dispatch/confirm
    Accept a unit_id, update the unit status to "dispatched", send an FCM
    push notification, and write an audit log entry.

Both endpoints require a valid Bearer token in the Authorization header.

Requirements: 4.1, 4.5
"""

from __future__ import annotations

import logging
import os
import time as _time
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from shared.models import (
    AuditEventType,
    AuditLogEntry,
    Location,
    ResponseUnit,
    UnitStatus,
    UnitType,
)
from .auth import verify_bearer_token
from .confirmation import (
    AuditLogger,
    FCMClient,
    MockAuditLogger,
    MockFCMClient,
    FirebaseFCMClient,
    confirm_dispatch,
)
from .maps_client import GoogleRoutesMapsClient, MapsClient, MockMapsClient
from .schemas import ConfirmRequest, ConfirmResponse, RecommendRequest, RecommendResponse
from .service import generate_recommendations
from .unit_store import FirebaseUnitStore, MockUnitStore, UnitStore

# ---------------------------------------------------------------------------
# Demo units — Chandigarh area (used when Firebase is not configured)
# ---------------------------------------------------------------------------

_DEMO_UNITS: list[ResponseUnit] = [
    ResponseUnit(
        unit_id="AMB_007",
        type=UnitType.AMBULANCE,
        status=UnitStatus.AVAILABLE,
        location=Location(lat=30.7340, lng=76.7820),
        hospital_or_station="PGIMER Chandigarh",
        capabilities=["CARDIAC", "TRAUMA"],
        last_updated=int(_time.time()),
    ),
    ResponseUnit(
        unit_id="AMB_012",
        type=UnitType.AMBULANCE,
        status=UnitStatus.AVAILABLE,
        location=Location(lat=30.7290, lng=76.7750),
        hospital_or_station="GMC Sector 32",
        capabilities=["GENERAL"],
        last_updated=int(_time.time()),
    ),
    ResponseUnit(
        unit_id="AMB_019",
        type=UnitType.AMBULANCE,
        status=UnitStatus.AVAILABLE,
        location=Location(lat=30.7380, lng=76.7700),
        hospital_or_station="GMSH Sector 16",
        capabilities=["PEDIATRIC", "TRAUMA"],
        last_updated=int(_time.time()),
    ),
    ResponseUnit(
        unit_id="FIRE_003",
        type=UnitType.FIRE_BRIGADE,
        status=UnitStatus.AVAILABLE,
        location=Location(lat=30.7400, lng=76.7900),
        hospital_or_station="Fire Station Sector 17",
        capabilities=["FIRE_RESCUE"],
        last_updated=int(_time.time()),
    ),
    ResponseUnit(
        unit_id="POL_021",
        type=UnitType.POLICE,
        status=UnitStatus.AVAILABLE,
        location=Location(lat=30.7310, lng=76.7800),
        hospital_or_station="Police Station Sector 11",
        capabilities=["GENERAL"],
        last_updated=int(_time.time()),
    ),
]


def _make_demo_unit_store() -> MockUnitStore:
    """Return a MockUnitStore seeded with Chandigarh demo units."""
    store = MockUnitStore()
    for u in _DEMO_UNITS:
        store.add_unit(u)
    return store


class _FallbackUnitStore:
    """Tries the primary (Firebase) unit store; falls back to demo units on any error.

    This allows the service to run for demos even when Firebase credentials
    are not yet configured, while transparently using real Firebase data
    once a valid serviceaccount.json is present.
    """

    def __init__(self, primary: UnitStore, fallback: MockUnitStore) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_all_units(self) -> list[ResponseUnit]:
        try:
            return await self._primary.get_all_units()
        except Exception as exc:
            logger.warning(
                "Firebase unit store unavailable (%s) — using demo units", exc
            )
            return await self._fallback.get_all_units()

    async def update_unit_status(self, unit_id: str, status: str) -> None:
        try:
            await self._primary.update_unit_status(unit_id, status)
        except Exception:
            await self._fallback.update_unit_status(unit_id, status)

    async def set_unit_dispatch(self, unit_id: str, dispatch_data: dict) -> None:
        try:
            await self._primary.set_unit_dispatch(unit_id, dispatch_data)
        except Exception:
            await self._fallback.set_unit_dispatch(unit_id, dispatch_data)

logger = logging.getLogger(__name__)


class AuditLogRequest(BaseModel):
    call_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "operator"
    timestamp: str | None = None


class OverrideLabelRequest(BaseModel):
    call_id: str
    operator_id: str
    original: dict[str, Any] = Field(default_factory=dict)
    overridden: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None

app = FastAPI(
    title="CrisisLink Dispatch Service",
    version="0.1.0",
    description=(
        "Queries available response units, calculates traffic-aware ETAs, "
        "ranks units by composite score, and manages dispatch confirmation."
    ),
)

# ---------------------------------------------------------------------------
# Dependency injection — swappable backends for testing / production
# ---------------------------------------------------------------------------

if os.environ.get("CRISISLINK_USE_REAL_SERVICES") == "true":
    _unit_store: UnitStore = _FallbackUnitStore(FirebaseUnitStore(), _make_demo_unit_store())
    _maps_client: MapsClient = GoogleRoutesMapsClient()
    _fcm_client: FCMClient = FirebaseFCMClient()
else:
    _unit_store = _make_demo_unit_store()
    _maps_client = MockMapsClient()
    _fcm_client = MockFCMClient()
_audit_logger: AuditLogger = MockAuditLogger()


def set_unit_store(store: UnitStore) -> None:
    """Replace the unit store (for testing or production wiring)."""
    global _unit_store
    _unit_store = store


def set_maps_client(client: MapsClient) -> None:
    """Replace the maps client."""
    global _maps_client
    _maps_client = client


def set_fcm_client(client: FCMClient) -> None:
    """Replace the FCM client."""
    global _fcm_client
    _fcm_client = client


def set_audit_logger(logger_impl: AuditLogger) -> None:
    """Replace the audit logger."""
    global _audit_logger
    _audit_logger = logger_impl


def get_unit_store() -> UnitStore:
    return _unit_store


def get_maps_client() -> MapsClient:
    return _maps_client


def get_fcm_client() -> FCMClient:
    return _fcm_client


def get_audit_logger() -> AuditLogger:
    return _audit_logger


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/calls/{call_id}/dispatch/recommend",
    response_model=RecommendResponse,
    summary="Generate ranked dispatch recommendations",
)
async def recommend(
    call_id: str,
    body: RecommendRequest,
    _token: str = Depends(verify_bearer_token),
) -> RecommendResponse:
    """Generate ranked dispatch recommendations for a call.

    Queries available units, calculates ETAs, ranks by composite score,
    and returns the top 3 recommendations as a Dispatch_Card.
    """
    card = await generate_recommendations(
        call_id=call_id,
        classification=body.classification,
        caller_location=body.caller_location,
        unit_store=_unit_store,
        maps_client=_maps_client,
    )

    return RecommendResponse(
        recommendations=card.recommendations,
        dispatch_card=card,
    )


@app.post(
    "/api/v1/calls/{call_id}/dispatch/confirm",
    response_model=ConfirmResponse,
    summary="Confirm dispatch of a unit",
)
async def confirm(
    call_id: str,
    body: ConfirmRequest,
    _token: str = Depends(verify_bearer_token),
) -> ConfirmResponse:
    """Confirm dispatch of a specific unit for a call.

    Updates the unit status, sends an FCM notification, and writes
    an audit log entry.
    """
    result = await confirm_dispatch(
        call_id=call_id,
        unit_id=body.unit_id,
        unit_store=_unit_store,
        fcm_client=_fcm_client,
        audit_logger=_audit_logger,
        dispatch_context={
            "emergency_type": body.emergency_type,
            "severity": body.severity,
            "caller_lat": body.caller_lat,
            "caller_lng": body.caller_lng,
            "key_facts": body.key_facts,
        },
    )

    return ConfirmResponse(status=result["status"], unit_id=result["unit_id"])


@app.post(
    "/api/v1/audit/log",
    summary="Record an operator/audit event",
)
async def audit_log(
    body: AuditLogRequest,
    _token: str = Depends(verify_bearer_token),
) -> dict[str, str]:
    """Write an audit event through the configured audit logger."""
    event_type = body.event_type
    if event_type not in {item.value for item in AuditEventType}:
        event_type = AuditEventType.ERROR.value

    entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        call_id=body.call_id,
        event_type=AuditEventType(event_type),
        payload=body.payload,
        actor=body.actor,
        timestamp=datetime.now(timezone.utc),
    )
    await _audit_logger.write_entry(entry)
    return {"status": "logged", "log_id": entry.log_id}


@app.get(
    "/api/v1/analytics/response-times",
    summary="Return response time analytics",
)
async def response_times(
    breakdown: str = "region",
    _token: str = Depends(verify_bearer_token),
) -> dict[str, list[dict[str, Any]]]:
    """Return analytics entries.

    This is a working MVP endpoint with deterministic empty-state data. It
    keeps the admin dashboard functional until BigQuery aggregation is wired.
    """
    return {
        "entries": [
            {
                "dimension": "No production data yet" if breakdown else "all",
                "avg_response_minutes": 0.0,
                "median_response_minutes": 0.0,
                "p95_response_minutes": 0.0,
                "total_incidents": 0,
            }
        ]
    }


@app.get(
    "/api/v1/analytics/classification-accuracy",
    summary="Return classification accuracy metrics",
)
async def classification_accuracy(
    _token: str = Depends(verify_bearer_token),
) -> dict[str, int]:
    return {"total_classifications": 0, "operator_overrides": 0}


@app.get(
    "/api/v1/analytics/trend-reports",
    summary="Return predictive trend reports",
)
async def trend_reports(
    _token: str = Depends(verify_bearer_token),
) -> dict[str, list[dict[str, Any]]]:
    return {"entries": []}


@app.post(
    "/api/v1/analytics/record-override",
    summary="Record an operator override for accuracy tracking",
)
async def record_override(
    body: OverrideLabelRequest,
    _token: str = Depends(verify_bearer_token),
) -> dict[str, str]:
    entry = AuditLogEntry(
        log_id=str(uuid.uuid4()),
        call_id=body.call_id,
        event_type=AuditEventType.OPERATOR_OVERRIDE,
        payload={
            "operator_id": body.operator_id,
            "original": body.original,
            "overridden": body.overridden,
        },
        actor=body.operator_id,
        timestamp=datetime.now(timezone.utc),
    )
    await _audit_logger.write_entry(entry)
    return {"status": "recorded", "log_id": entry.log_id}
