from typing import Protocol

from app.services.ai.mock import MockAIProvider


class AIProvider(Protocol):
    def extract(self, text: str) -> object:
        """Return untrusted structured data, validated by the application service."""
        ...


class AIProviderUnavailableError(Exception):
    pass


def create_provider(name: str) -> AIProvider:
    if name.strip().casefold() in {"mock", "fake"}:
        return MockAIProvider()
    raise AIProviderUnavailableError("Provider AI non disponibile. Usa l'inserimento manuale.")
