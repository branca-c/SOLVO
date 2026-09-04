from fastapi import APIRouter

from app.schemas.health import HealthResponse

api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
