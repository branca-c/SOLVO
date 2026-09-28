import json
from io import BytesIO

import httpx
import pytest

from app.domain.description_grounding import segment_source
from app.models import Category
from app.services.ai.provider import create_provider
from app.services.audio_drafts import build_audio_draft
from app.services.transcription import (
    DEFAULT_GROQ_TRANSCRIPTION_MODEL,
    GroqTranscriptionProvider,
    MockTranscriptionProvider,
    TranscriptionUnavailableError,
    create_transcription_provider,
)


API_KEY = "gsk_transcription_test_secret"
AUDIO = b"webm audio bytes"
TRANSCRIPT = "Il climatizzatore perde acqua in via Libertà 85."
DRAFT_RESULT = {
    "fault_address": "Via Libertà 85",
    "category_name": "Climatizzazione",
    "priority": "MEDIA",
    "description": "Il climatizzatore perde acqua.",
    "warnings": [],
}


class FakeSession:
    def __init__(self, categories):
        self.categories = categories

    def scalars(self, statement):
        return self.categories


def install_http(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )


def transcription_provider():
    return create_transcription_provider(
        "groq", "", groq_api_key=API_KEY,
    )


def test_factory_selects_groq_and_keeps_mock_provider():
    provider = transcription_provider()

    assert isinstance(provider, GroqTranscriptionProvider)
    assert provider.model == DEFAULT_GROQ_TRANSCRIPTION_MODEL
    assert isinstance(create_transcription_provider("mock", "Demo"), MockTranscriptionProvider)
    assert create_transcription_provider("mock", "Demo").transcribe(b"audio", "audio/webm") == "Demo"


def test_groq_transcription_missing_key_fails_safely():
    with pytest.raises(TranscriptionUnavailableError, match="GROQ_API_KEY") as exc:
        create_transcription_provider("groq", "")

    assert API_KEY not in str(exc.value)


def test_groq_transcription_sends_authorized_multipart_audio_model_and_language(monkeypatch):
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://api.groq.com/openai/v1/audio/transcriptions"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        body = request.content
        assert API_KEY.encode() not in body
        assert AUDIO in body
        assert b'name="file"' in body
        assert b'name="model"' in body
        assert b"configured-whisper" in body
        assert b'name="language"' in body
        assert b"it" in body
        return httpx.Response(200, json={"text": f"  {TRANSCRIPT}  "})

    install_http(monkeypatch, handler)
    provider = create_transcription_provider(
        "groq", "", groq_api_key=API_KEY, groq_model="configured-whisper",
    )

    assert provider.transcribe(AUDIO, "audio/webm") == TRANSCRIPT


@pytest.mark.parametrize(("failure", "message"), [
    ("connect", "non raggiungibile"),
    ("timeout", "scaduto"),
    (401, "non ha completato"),
    (500, "non ha completato"),
    ("malformed", "Risposta Groq"),
    ("missing_text", "Risposta Groq"),
])
def test_groq_transcription_failures_are_sanitized_without_logging_key(
    monkeypatch, caplog, failure, message,
):
    def handler(request):
        if failure == "connect":
            raise httpx.ConnectError(f"leaked {API_KEY}", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout(f"leaked {API_KEY}", request=request)
        if failure == "malformed":
            return httpx.Response(200, text="not JSON")
        if failure == "missing_text":
            return httpx.Response(200, json={})
        return httpx.Response(failure, json={"error": f"leaked {API_KEY}"})

    install_http(monkeypatch, handler)
    with pytest.raises(TranscriptionUnavailableError, match=message) as exc:
        transcription_provider().transcribe(AUDIO, "audio/webm")

    assert API_KEY not in str(exc.value)
    assert API_KEY not in caplog.text


def test_audio_flow_uses_one_groq_transcription_then_one_existing_groq_draft(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/openai/v1/audio/transcriptions":
            assert AUDIO in request.content
            return httpx.Response(200, json={"text": TRANSCRIPT})
        assert request.url.path == "/openai/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-120b"
        assert body["messages"][1]["content"] == TRANSCRIPT
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(DRAFT_RESULT)}}],
        })

    install_http(monkeypatch, handler)
    result = build_audio_draft(
        BytesIO(AUDIO),
        "audio/webm",
        FakeSession([Category(id=7, name="Climatizzazione")]),
        create_provider("groq", groq_api_key=API_KEY),
        transcription_provider(),
        10,
    )

    assert len(calls) == 2
    assert result.transcript == TRANSCRIPT
    assert result.transcription_source == "groq"
    assert result.draft.description == DRAFT_RESULT["description"]
    assert result.draft.category_id == 7
    assert all(request.url.path in {
        "/openai/v1/audio/transcriptions", "/openai/v1/chat/completions",
    } for request in calls)
