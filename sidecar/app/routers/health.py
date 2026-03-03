"""
Health check router for the Stratum Data Sidecar.
Phase 2 | Plan 01
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Liveness probe — returns 200 OK when the sidecar is running."""
    return HealthResponse(status="ok", service="data-sidecar")
