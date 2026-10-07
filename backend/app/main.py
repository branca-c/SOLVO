from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.demo_access import DEMO_ACCESS_HEADER, has_demo_access, is_public_api_path
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", DEMO_ACCESS_HEADER],
    )

    @application.middleware("http")
    async def demo_access_gate(request, call_next):
        # Preflight must reach CORS middleware. Health is outside /api; signed
        # technician actions and the Telegram webhook have their own checks.
        if (
            request.method != "OPTIONS"
            and request.url.path.startswith("/api")
            and not is_public_api_path(request.url.path)
            and not has_demo_access(request.headers.get(DEMO_ACCESS_HEADER), get_settings())
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Accesso demo non autorizzato."},
                headers={"Cache-Control": "no-store"},
            )
        return await call_next(request)

    application.include_router(api_router)
    return application


app = create_app()
