"""Bearer token authentication dependency for the Intelligence Service.

Reuses the same pattern as ``speech_ingestion.auth`` — a single
environment-configurable token validated via FastAPI's ``HTTPBearer``
security scheme.
"""

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Configurable via environment variable; defaults to a development token.
_EXPECTED_TOKEN = os.environ.get("CRISISLINK_API_TOKEN", "crisislink-dev-token")

_bearer_scheme = HTTPBearer()


async def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """Validate the Bearer token from the Authorization header.

    Returns the token string on success.
    Raises 401 if the token is missing or does not match the expected value.
    """
    if credentials.credentials != _EXPECTED_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
