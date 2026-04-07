from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.runtime_attestation import build_runtime_attestation

router = APIRouter(prefix="/v1", tags=["attestation"])


@router.get("/attestation")
def get_runtime_attestation() -> dict[str, Any]:
    try:
        return build_runtime_attestation()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"runtime attestation failed: {exc}") from exc
