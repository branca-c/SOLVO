import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import pytest
from pydantic import ValidationError

from app.api import ai as ai_api
from app.core.config import Settings, get_settings
from app.main import create_app
from app.services import assignment_notifications


NEON_URL = "postgresql://neon_user:neon_password@example.neon.tech/neondb?sslmode=require"


def test_standard_neon_database_url_uses_installed_psycopg_driver():
    settings = Settings(_env_file=None, database_url=NEON_URL)

    assert settings.sqlalchemy_database_url == (
        "postgresql+psycopg://neon_user:neon_password@example.neon.tech/neondb?sslmode=require"
    )


def test_sqlite_database_url_is_limited_to_explicit_test_environment():
    settings = Settings(_env_file=None, app_env="test", database_url="sqlite:////tmp/solvo-e2e.sqlite3")

    assert settings.sqlalchemy_database_url == "sqlite:////tmp/solvo-e2e.sqlite3"
    with pytest.raises(ValidationError, match="SQLite è consentito solo"):
        Settings(_env_file=None, database_url="sqlite:////tmp/solvo-e2e.sqlite3")


def test_comma_separated_cors_origins_keep_local_development_origins():
    settings = Settings(
        _env_file=None,
        database_url=NEON_URL,
        cors_allowed_origins="http://localhost:5173, https://solvo-frontend.onrender.com ,http://127.0.0.1:5173",
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://solvo-frontend.onrender.com",
        "http://127.0.0.1:5173",
    ]


def test_cors_rejects_wildcard_with_credentials():
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(_env_file=None, database_url=NEON_URL, cors_allowed_origins="*")


def test_configured_cors_origin_is_applied_to_preflight(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", NEON_URL)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://solvo-frontend.onrender.com")
    get_settings.cache_clear()
    try:
        async def preflight():
            transport = ASGITransport(app=create_app())
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.options(
                    "/health",
                    headers={
                        "Origin": "https://solvo-frontend.onrender.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )

        response = asyncio.run(preflight())
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://solvo-frontend.onrender.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_health_is_lightweight_and_does_not_initialize_providers(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise AssertionError("Provider initialization is not allowed for /health")

    monkeypatch.setattr(ai_api, "create_provider", unavailable)
    monkeypatch.setattr(ai_api, "create_transcription_provider", unavailable)
    monkeypatch.setattr(assignment_notifications, "create_notification_provider", unavailable)

    async def health():
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_groq_production_selection_does_not_require_ollama_or_local_whisper_at_startup(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", NEON_URL)
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        async def health():
            transport = ASGITransport(app=create_app())
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/health")

        response = asyncio.run(health())
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200


def test_groq_configuration_defaults_remain_available():
    settings = Settings(
        _env_file=None,
        database_url=NEON_URL,
        groq_api_key="test-key",
        ai_provider="groq",
        transcription_provider="groq",
    )

    assert settings.ai_provider == "groq"
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.transcription_provider == "groq"
    assert settings.groq_transcription_model == "whisper-large-v3-turbo"
    assert settings.groq_api_key.get_secret_value() == "test-key"


def test_render_blueprint_has_backend_commands_and_no_tunnel_hostname():
    blueprint = (Path(__file__).parents[2] / "render.yaml").read_text(encoding="utf-8")

    assert "rootDir: backend" in blueprint
    assert "buildCommand: pip install -r requirements.txt && alembic upgrade head" in blueprint
    assert "preDeployCommand:" not in blueprint
    assert "PYTHON_VERSION" in blueprint
    assert "startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "trycloudflare.com" not in blueprint
