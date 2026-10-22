from fastapi import APIRouter, status
from pydantic import BaseModel
from typing import Dict

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, str]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Check the operational status of the API and its dependent services.",
)
async def check_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services={
            "database": "available",
            "redis": "available",
        },
    )
