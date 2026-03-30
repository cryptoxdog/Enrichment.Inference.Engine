"""
app/core/auth.py
API key authentication dependency.
"""

from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> str:
    if not credentials or credentials.credentials != settings.enrich_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return credentials.credentials
