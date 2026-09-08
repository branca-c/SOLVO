"""Temporary audio input; providers have no access to persistence."""
from typing import Protocol


class TranscriptionUnavailableError(Exception):
    pass


class TranscriptionProvider(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> str: ...


class MockTranscriptionProvider:
    def __init__(self, text: str):
        self.text = text

    def transcribe(self, audio: bytes, content_type: str) -> str:
        return self.text


def create_transcription_provider(name: str, mock_text: str) -> TranscriptionProvider:
    if name.strip().casefold() in {"mock", "fake"}:
        return MockTranscriptionProvider(mock_text)
    raise TranscriptionUnavailableError("Provider di trascrizione non disponibile.")
