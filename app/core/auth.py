"""
API key authentication — constant-time SHA-256 hash comparison.
Salesforce Named Credential and Odoo ir.config_parameter both
store and send the raw key; we only store the hash.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import get_settings

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: Annotated[str | None, Security(_header)],
) -> str:
    """Validate API key via constant-time hash comparison."""
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")

    provided_hash = hashlib.sha256(api_key.encode()).hexdigest()

    if not hmac.compare_digest(provided_hash, get_settings().api_key_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid API key")

    return api_key
