from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.core.config import DEFAULT_OLLAMA_KEEP_ALIVE
from app.domain.description_grounding import SourceSegment


@dataclass(frozen=True)
class DraftExtraction:
    """One semantic draft-extraction operation, independent of provider internals."""

    structured: object
    description: str | None = None
    fault_quotes: object | None = None


class AIProvider(Protocol):
    def extract_draft(
        self, text: str, categories: list[str], segments: Sequence[SourceSegment],
    ) -> DraftExtraction:
        """Return one untrusted draft proposal through provider-specific internals."""
        ...


class AIProviderUnavailableError(Exception):
    pass


class InvalidAIOutputError(Exception):
    pass


def create_provider(
    name: str, *, base_url: str = "http://127.0.0.1:11434",
    model: str = "", timeout: float = 60, keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE,
    groq_api_key: str = "", groq_base_url: str = "https://api.groq.com/openai/v1",
    groq_model: str = "openai/gpt-oss-120b", groq_timeout: float = 60,
) -> AIProvider:
    if name.strip().casefold() in {"mock", "fake"}:
        from app.services.ai.mock import MockAIProvider
        return MockAIProvider()
    if name.strip().casefold() == "ollama":
        from app.services.ai.ollama import OllamaAIProvider
        return OllamaAIProvider(base_url, model, timeout, keep_alive=keep_alive)
    if name.strip().casefold() == "groq":
        from app.services.ai.groq import GroqAIProvider
        return GroqAIProvider(groq_base_url, groq_api_key, groq_model, groq_timeout)
    raise AIProviderUnavailableError("Provider AI non disponibile. Usa l'inserimento manuale.")
