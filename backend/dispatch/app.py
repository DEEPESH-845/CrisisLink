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

from fastapi import Depends, FastAPI

from .auth import verify_bearer_token
from .confirmation import (
    AuditLogger,
    FCMClient,
    MockAuditLogger,
    MockFCMClient,
    confirm_dispatch,
)
from .maps_client import MapsClient, MockMapsClient
from .schemas import ConfirmRequest, ConfirmResponse, RecommendRequest, RecommendResponse
from .service import generate_recommendations
from .unit_store import MockUnitStore, UnitStore

logger = logging.getLogger(__name__)

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

_unit_store: UnitStore = MockUnitStore()
_maps_client: MapsClient = MockMapsClient()
_fcm_client: FCMClient = MockFCMClient()
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
    )

    return ConfirmResponse(status=result["status"], unit_id=result["unit_id"])
