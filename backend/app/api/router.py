from fastapi import APIRouter

from app.api.public_assignments import router as public_assignments_router
from app.api.realtime import router as realtime_router
from app.api.ai import router as ai_router
from app.api.assignments import router as assignments_router
from app.api.work_orders import router as work_orders_router
from app.schemas.health import HealthResponse

api_router = APIRouter()
api_router.include_router(realtime_router)
api_router.include_router(public_assignments_router)
api_router.include_router(work_orders_router)
api_router.include_router(assignments_router)
api_router.include_router(ai_router)


@api_router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
