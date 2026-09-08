from fastapi import APIRouter

from app.api.work_orders import router as work_orders_router
from app.schemas.health import HealthResponse

api_router = APIRouter()
api_router.include_router(work_orders_router)


@api_router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
