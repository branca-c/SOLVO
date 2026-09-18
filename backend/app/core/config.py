from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OLLAMA_KEEP_ALIVE = "30m"

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
    notification_provider: str = "mock"
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_demo_chat_id: str = ""
    ai_provider: str = "mock"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: float = 60
    ollama_keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE
    transcription_provider: str = "mock"
    transcription_mock_text: str = "Perdita di acqua dal tubo del bagno."
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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
