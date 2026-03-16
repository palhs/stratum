"""
Health router — GET /health endpoint for reasoning-engine service.
"""
from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok", service="reasoning-engine")
