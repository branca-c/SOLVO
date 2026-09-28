from collections.abc import Sequence
from typing import Protocol

from app.core.config import DEFAULT_OLLAMA_KEEP_ALIVE
from app.domain.description_grounding import SourceSegment
from app.services.ai.mock import MockAIProvider


class AIProvider(Protocol):
    def extract_structured(self, text: str, categories: list[str]) -> object:
        """Return untrusted scalar extraction data."""
        ...

    def select_fault_quotes(self, segments: Sequence[SourceSegment]) -> object:
        """Return untrusted exact quote selections."""
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
