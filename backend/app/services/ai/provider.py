from typing import Protocol

from app.core.config import DEFAULT_OLLAMA_KEEP_ALIVE
from app.services.ai.mock import MockAIProvider


class AIProvider(Protocol):
    def extract(self, text: str, categories: list[str]) -> object:
        """Return untrusted structured data, validated by the application service."""
        ...


class AIProviderUnavailableError(Exception):
    pass


class InvalidAIOutputError(Exception):
    pass


def create_provider(
    name: str, *, base_url: str = "http://127.0.0.1:11434",
    model: str = "", timeout: float = 60, keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE,
) -> AIProvider:
    if name.strip().casefold() in {"mock", "fake"}:
        return MockAIProvider()
    if name.strip().casefold() == "ollama":
        from app.services.ai.ollama import OllamaAIProvider
        return OllamaAIProvider(base_url, model, timeout, keep_alive=keep_alive)
    raise AIProviderUnavailableError("Provider AI non disponibile. Usa l'inserimento manuale.")
