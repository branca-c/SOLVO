from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.demo_access import (
    DEMO_ACCESS_HEADER,
    DEMO_SESSION_HEADER,
    has_demo_access,
    is_public_api_path,
    is_session_exempt_api_path,
    demo_session_generation,
    demo_session_write_fence,
    requires_demo_session_write_fence,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import demo_sessions
from app.services.demo_sessions import DemoSessionUnauthorizedError, require_active
from app.services.realtime import manager


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
    )
    application.state.session_factory = SessionLocal

    def resolve_active_demo_generation() -> tuple[bool, int | None]:
        current_settings = get_settings()
        with application.state.session_factory() as db:
            return (
                current_settings.solvo_demo_session_enabled,
                demo_sessions.active_generation(db, current_settings),
            )

    manager.set_generation_resolver(resolve_active_demo_generation)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type", "Authorization", DEMO_ACCESS_HEADER, DEMO_SESSION_HEADER,
        ],
    )

    @application.middleware("http")
    async def demo_access_gate(request, call_next):
        # Preflight must reach CORS middleware. Health is outside /api; signed
        # technician actions and the Telegram webhook have their own checks.
        protected = (
            request.method != "OPTIONS"
            and request.url.path.startswith("/api")
            and not is_public_api_path(request.url.path)
        )
        current_settings = get_settings()
        if protected and not has_demo_access(
            request.headers.get(DEMO_ACCESS_HEADER), current_settings
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Accesso demo non autorizzato."},
                headers={"Cache-Control": "no-store"},
            )
        if (
            protected
            and current_settings.solvo_demo_session_enabled
            and not is_session_exempt_api_path(request.url.path)
        ):
            try:
                with application.state.session_factory() as db:
                    active_session = require_active(
                        db, request.headers.get(DEMO_SESSION_HEADER), current_settings
                    )
                    generation = active_session.generation
            except DemoSessionUnauthorizedError as exc:
                return JSONResponse(
                    status_code=401,
                    content={"detail": str(exc)},
                    headers={"Cache-Control": "no-store"},
                )
            generation_token = demo_session_generation.set(generation)
            write_token = demo_session_write_fence.set(
                requires_demo_session_write_fence(request.method, request.url.path)
            )
            try:
                return await call_next(request)
            finally:
                demo_session_write_fence.reset(write_token)
                demo_session_generation.reset(generation_token)
        return await call_next(request)

    @application.exception_handler(DemoSessionUnauthorizedError)
    async def stale_demo_session_handler(_request, exc):
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"Cache-Control": "no-store"},
        )

    application.include_router(api_router)
    return application


app = create_app()
