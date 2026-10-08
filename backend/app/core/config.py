from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OLLAMA_KEEP_ALIVE = "30m"
DEFAULT_CORS_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "SOLVO API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = False
    app_log_level: str = "INFO"
    database_url: str
    cors_allowed_origins: str = DEFAULT_CORS_ALLOWED_ORIGINS
    solvo_demo_access_enabled: bool = False
    solvo_demo_access_key: SecretStr = SecretStr("")
    solvo_demo_session_enabled: bool = False
    solvo_demo_session_idle_minutes: int = Field(default=10, ge=1, le=120)
    assignment_action_secret: SecretStr = SecretStr("")
    technician_action_base_url: str = "http://127.0.0.1:5173"
    technician_action_token_ttl_minutes: int = Field(default=1440, ge=1, le=10080)
    notification_provider: str = "mock"
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_demo_chat_id: str = ""
    telegram_bot_username: str = ""
    telegram_binding_secret: SecretStr = SecretStr("")
    telegram_webhook_secret: SecretStr = SecretStr("")
    telegram_binding_token_ttl_minutes: int = Field(default=15, ge=1, le=1440)
    ai_provider: str = "mock"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: float = 60
    ollama_keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE
    groq_api_key: SecretStr = SecretStr("")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout_seconds: float = 60
    transcription_provider: str = "mock"
    transcription_mock_text: str = "Perdita di acqua dal tubo del bagno."
    groq_transcription_model: str = "whisper-large-v3-turbo"
    whisper_model_size: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_language: str = "it"
    whisper_beam_size: int = Field(default=5, ge=1)
    max_audio_upload_mb: int = Field(default=10, ge=1, le=25)

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ALLOWED_ORIGINS deve contenere almeno un'origine HTTP/HTTPS.")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                origin == "*" or parsed.scheme not in {"http", "https"}
                or not parsed.netloc or parsed.path or parsed.query or parsed.fragment
            ):
                raise ValueError("CORS_ALLOWED_ORIGINS accetta solo origini HTTP/HTTPS esplicite.")
        return ",".join(origins)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str, info: ValidationInfo) -> str:
        parsed = urlsplit(value)
        if parsed.scheme in {"postgresql", "postgresql+psycopg"} and parsed.hostname:
            return value
        if info.data.get("app_env") == "test" and value.startswith("sqlite:///"):
            return value
        raise ValueError("DATABASE_URL deve essere un URL PostgreSQL; SQLite è consentito solo con APP_ENV=test.")

    @property
    def cors_origins(self) -> list[str]:
        return self.cors_allowed_origins.split(",")

    @property
    def sqlalchemy_database_url(self) -> str:
        """Use the installed psycopg driver for standard PostgreSQL/Neon URLs."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
