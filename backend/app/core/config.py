from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "SOLVO API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = False
    app_log_level: str = "INFO"
    database_url: PostgresDsn
    assignment_action_secret: SecretStr = SecretStr("")
    technician_action_base_url: str = "http://127.0.0.1:5173"
    technician_action_token_ttl_minutes: int = Field(default=1440, ge=1, le=10080)
    whatsapp_provider: str = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_whatsapp_from: str = ""
    ai_provider: str = "mock"
    transcription_provider: str = "mock"
    transcription_mock_text: str = "Perdita di acqua dal tubo del bagno."
    max_audio_upload_mb: int = Field(default=10, ge=1, le=25)

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
