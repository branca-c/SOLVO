import json

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.ai import get_transcription_provider
from app.core.config import get_settings
from app.models import Category
from app.services.ai.mock import MockAIProvider
from app.services.ai.ollama import OllamaAIProvider
from app.services.ai.provider import (
    AIProviderUnavailableError, InvalidAIOutputError, create_provider,
)

TEXT = ("Sono Anna Bianchi, telefono 3471234567. Il guasto è in via Libertà 85. "
        "Il climatizzatore perde acqua e non raffredda.")
RESULT = {
    "user_first_name": "Anna", "user_last_name": "Bianchi",
    "user_phone": "3471234567", "user_email": None,
    "fault_address": "Via Libertà 85", "category_name": "Climatizzazione",
    "priority": "MEDIA",
    "description": "Perdita d'acqua dal climatizzatore e mancato raffreddamento.",
}


def install_http(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(
            **kwargs, transport=httpx.MockTransport(handler),
        ),
    )


def response(data):
    return httpx.Response(200, json={"message": {"content": json.dumps(data)}})


def test_factory_selects_explicit_provider():
    assert isinstance(create_provider("mock"), MockAIProvider)
    assert isinstance(create_provider("ollama", model="installed-model"), OllamaAIProvider)


@pytest.mark.parametrize("kwargs,message", [
    ({}, "OLLAMA_MODEL"), ({"model": " "}, "OLLAMA_MODEL"),
    ({"model": "test", "base_url": "file:///tmp/model"}, "OLLAMA_BASE_URL"),
    ({"model": "test", "timeout": 0}, "OLLAMA_TIMEOUT_SECONDS"),
    ({"model": "test", "timeout": float("nan")}, "OLLAMA_TIMEOUT_SECONDS"),
])
def test_configuration(kwargs, message):
    with pytest.raises(AIProviderUnavailableError, match=message):
        create_provider("ollama", **kwargs)


@pytest.mark.parametrize("priority", ["PROGRAMMABILE", "BASSA", "MEDIA", "ALTA", "URGENTE", None])
def test_structured_schema_and_priority(monkeypatch, priority):
    def handler(request):
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "configured-model"
        assert body["stream"] is False
        assert body["format"]["additionalProperties"] is False
        assert body["format"]["properties"]["category_name"]["anyOf"][0]["enum"] == ["Climatizzazione"]
        assert body["messages"][1]["content"] == TEXT
        assert "URGENTE" in body["messages"][0]["content"]
        return response({**RESULT, "priority": priority})
    install_http(monkeypatch, handler)
    result = create_provider("ollama", model="configured-model").extract(TEXT, ["Climatizzazione"])
    assert result["priority"] == priority
    for key, value in RESULT.items():
        if key != "priority":
            assert result[key] == value


@pytest.mark.parametrize("data", [{}, {"user_first_name": None, "description": None}])
def test_missing_values_remain_null(monkeypatch, data):
    install_http(monkeypatch, lambda request: response(data))
    result = create_provider("ollama", model="test").extract("Ciao", [])
    for key in ("user_first_name", "user_last_name", "user_phone", "fault_address", "description", "priority"):
        assert result[key] is None


@pytest.mark.parametrize("reply", [
    httpx.Response(200, text="not JSON"),
    httpx.Response(200, json={"message": {"content": "```json\n{}\n```"}}),
    httpx.Response(200, json={"message": {"content": "{bad"}}),
    httpx.Response(200, json={}), httpx.Response(200, json=[]),
    response({"priority": "CRITICA"}), response({"category_id": 3}),
    response({"user_phone": []}),
])
def test_invalid_output_controlled(monkeypatch, reply):
    install_http(monkeypatch, lambda request: reply)
    with pytest.raises(InvalidAIOutputError):
        create_provider("ollama", model="test").extract(TEXT, [])


@pytest.mark.parametrize("field", ["user_first_name", "user_last_name", "user_phone", "user_email", "fault_address"])
def test_contact_repetition_rejected_without_text_mangling(monkeypatch, field):
    data = {**RESULT, "user_email": "anna@example.com"}
    data["description"] = f"{data[field]} segnala perdita dal climatizzatore."
    install_http(monkeypatch, lambda request: response(data))
    with pytest.raises(InvalidAIOutputError, match="ripete"):
        create_provider("ollama", model="test").extract(TEXT, [])


@pytest.mark.parametrize("failure,message", [
    ("connect", "non raggiungibile"), ("timeout", "scaduto"),
    (404, "Modello"), (500, "completato"),
])
def test_network_errors_sanitized(monkeypatch, failure, message):
    def handler(request):
        if failure == "connect":
            raise httpx.ConnectError("private details", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private details", request=request)
        return httpx.Response(failure, json={"error": "private details"})
    install_http(monkeypatch, handler)
    with pytest.raises(AIProviderUnavailableError, match=message) as exc:
        create_provider("ollama", model="test").extract(TEXT, [])
    assert "private" not in str(exc.value)


@pytest.fixture
def ollama_api(api, monkeypatch):
    client, engine = api
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "configured-model")
    with Session(engine) as db:
        db.add(Category(id=73, name="Climatizzazione"))
        db.commit()
    return client, engine


def test_text_and_whisper_transcript_share_extraction_without_writes(ollama_api, monkeypatch):
    client, engine = ollama_api
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert "Climatizzazione" in body["format"]["properties"]["category_name"]["anyOf"][0]["enum"]
        return response(RESULT)
    install_http(monkeypatch, handler)
    # Substitute only the speech-to-text port; extraction is the real Ollama adapter.
    class Transcript:
        def transcribe(self, content, mime):
            return TEXT
    client.app.dependency_overrides[get_transcription_provider] = lambda: Transcript()
    statements = []
    def observe(conn, cursor, statement, *args):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", observe)
    try:
        typed = client.post("/api/ai/work-order-draft", json={"text": TEXT})
        spoken = client.post("/api/ai/work-order-draft-audio", files={"audio": ("fault.webm", b"audio", "audio/webm")})
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert typed.status_code == spoken.status_code == 200
    assert typed.json() == spoken.json()["draft"]
    assert typed.json()["category_id"] == 73
    assert requests[0] == requests[1]
    assert statements and set(statements) == {"SELECT"}
    assert client.get("/api/work-orders").json() == []


@pytest.mark.parametrize("result", [{}, {**RESULT, "category_name": "Non configurata"}])
def test_backend_missing_and_unresolved_warnings(ollama_api, monkeypatch, result):
    client, _ = ollama_api
    install_http(monkeypatch, lambda request: response(result))
    draft = client.post("/api/ai/work-order-draft", json={"text": TEXT}).json()
    assert draft["category_name"] == "Climatizzazione"
    assert draft["category_id"] is not None
    assert draft["warnings"]
    if not result:
        assert draft["description"] == ""
        assert draft["user_phone"] is None


@pytest.mark.parametrize("audio", [False, True])
def test_bad_output_returns_502_for_both_routes(ollama_api, monkeypatch, audio):
    client, _ = ollama_api
    install_http(monkeypatch, lambda request: response({"priority": "CRITICA"}))
    class Transcript:
        def transcribe(self, content, mime):
            return TEXT
    client.app.dependency_overrides[get_transcription_provider] = lambda: Transcript()
    if audio:
        result = client.post("/api/ai/work-order-draft-audio", files={"audio": ("fault.wav", b"audio", "audio/wav")})
    else:
        result = client.post("/api/ai/work-order-draft", json={"text": TEXT})
    assert result.status_code == 502
    assert client.get("/api/work-orders").json() == []


def test_missing_model_visible_as_configuration_error(ollama_api, monkeypatch):
    client, _ = ollama_api
    monkeypatch.setattr(get_settings(), "ollama_model", "")
    result = client.post("/api/ai/work-order-draft", json={"text": TEXT})
    assert result.status_code == 503
    assert "OLLAMA_MODEL" in result.json()["detail"]


def test_natural_mario_request_preserves_city_and_formatted_phone(ollama_api, monkeypatch):
    client, engine = ollama_api
    with Session(engine) as db:
        db.add(Category(id=89, name="Ascensore"))
        db.commit()
    text = ("Mi chiamo Mario Rossi, il mio numero è 333 123 4567. "
            "Il guasto è in via Roma 20 a Palermo. "
            "L'ascensore è fermo al terzo piano e non riparte.")
    data = {
        "user_first_name": "Mario", "user_last_name": "Rossi",
        "user_phone": "3331234567", "fault_address": "Via Roma 20, Palermo",
        "category_name": "Ascensore", "priority": "ALTA",
        "description": "Ascensore fermo al terzo piano e non riparte.",
    }
    install_http(monkeypatch, lambda request: response(data))
    draft = client.post("/api/ai/work-order-draft", json={"text": text}).json()
    assert all(draft[key] == value for key, value in data.items())
    assert draft["category_id"] == 89


@pytest.mark.parametrize("location,address", [
    ("via Roma 20 a Palermo", "Via Roma 20, Palermo"),
    ("via Libertà 15, Palermo", "Via Libertà 15, Palermo"),
    ("corso Italia 8 a Bagheria, PA", "Corso Italia 8, Bagheria, PA"),
    ("corso Italia 8 a Bagheria, PA, 90011", "Corso Italia 8, Bagheria, PA, 90011"),
    ("via Dante 10", "Via Dante 10"),
])
def test_complete_fault_address_instructions_and_draft_retention(
    ollama_api, monkeypatch, location, address,
):
    """Check the actual prompt and grounding; model responses are deterministic fixtures."""
    client, _ = ollama_api
    text = (f"Sono Chiara Bianchi, telefono 3331234567. Il guasto è in {location}. "
            "L'ascensore è bloccato al terzo piano e non riparte.")
    description = "Ascensore bloccato al terzo piano e non riparte."

    def handler(request):
        body = json.loads(request.content)
        prompt = body["messages"][0]["content"]
        assert "posizione del guasto più completa esplicitamente presente" in prompt
        assert "via/luogo, numero civico, città/località, provincia e CAP" in prompt
        assert "Non inventare città, provincia o CAP" in prompt
        assert "non dedurre Palermo dal contesto" in prompt
        assert "non geocodificare e non usare servizi esterni" in prompt
        assert "telefono o email del richiedente in fault_address" in prompt
        assert "description deve essere una breve sintesi tecnica del solo guasto/intervento" in prompt
        if "90011" not in location:
            assert f"'{location}' -> '{address}'" in prompt
        assert body["messages"][1]["content"] == text
        return response({
            "user_first_name": "Chiara", "user_last_name": "Bianchi",
            "user_phone": "3331234567", "fault_address": address,
            "description": description,
        })

    install_http(monkeypatch, handler)
    result = client.post("/api/ai/work-order-draft", json={"text": text})
    assert result.status_code == 200
    draft = result.json()
    assert draft["fault_address"] == address
    assert draft["description"] == description
    assert draft["user_first_name"] == "Chiara"
    assert draft["user_phone"] == "3331234567"
    if location == "via Dante 10":
        assert "Palermo" not in draft["fault_address"]


def test_fault_address_with_invented_city_is_excluded(ollama_api, monkeypatch):
    client, _ = ollama_api
    install_http(monkeypatch, lambda request: response({
        "fault_address": "Via Dante 10, Palermo",
        "description": "Ascensore bloccato al terzo piano.",
    }))
    result = client.post("/api/ai/work-order-draft", json={
        "text": "Il guasto è in via Dante 10. L'ascensore è bloccato al terzo piano.",
    })
    assert result.status_code == 200
    assert result.json()["fault_address"] is None
    assert "Un dato non presente nel testo è stato escluso dalla bozza." in result.json()["warnings"]


def test_model_warnings_do_not_hide_missing_required_fields(ollama_api, monkeypatch):
    client, _ = ollama_api
    install_http(monkeypatch, lambda request: response({"warnings": [f"Avviso {i}" for i in range(10)]}))
    draft = client.post("/api/ai/work-order-draft", json={"text": TEXT}).json()
    assert any("richiedente" in warning for warning in draft["warnings"])
    assert any("Descrizione" in warning for warning in draft["warnings"])


@pytest.mark.parametrize('keep_alive', ['30m', '2m', '0', '-1'])
def test_configured_keep_alive_and_timing_leave_api_response_unchanged(
    ollama_api, monkeypatch, caplog, keep_alive,
):
    client, _ = ollama_api
    monkeypatch.setenv('OLLAMA_KEEP_ALIVE', keep_alive)
    from app.core.config import Settings
    configured = Settings(_env_file=None)
    assert configured.ollama_keep_alive == keep_alive
    monkeypatch.setattr(get_settings(), 'ollama_keep_alive', configured.ollama_keep_alive)
    monkeypatch.setattr(get_settings(), 'ollama_model', 'qwen2.5:7b')
    calls = []

    def handler(request):
        body = json.loads(request.content)
        assert body['keep_alive'] == keep_alive
        assert 'keep_alive' not in body['options']
        assert body['model'] == 'qwen2.5:7b'
        calls.append(body)
        return response(RESULT)

    install_http(monkeypatch, handler)

    class Transcript:
        def transcribe(self, content, mime):
            return TEXT

    client.app.dependency_overrides[get_transcription_provider] = lambda: Transcript()
    with caplog.at_level('INFO', logger='uvicorn.error.solvo.timing'):
        typed = client.post('/api/ai/work-order-draft', json={'text': TEXT})
        spoken = client.post('/api/ai/work-order-draft-audio', files={
            'audio': ('fault.wav', b'audio', 'audio/wav'),
        })
    expected = {
        **RESULT,
        'category_id': 73,
        'description': 'Il climatizzatore perde acqua e non raffredda.',
        'warnings': [],
    }
    assert typed.status_code == spoken.status_code == 200
    assert typed.json() == expected
    assert spoken.json() == {
        'transcript': TEXT, 'draft': expected, 'transcription_source': None,
    }
    assert len(calls) == 2  # No preload or other model request.
    records = [r for r in caplog.records if r.name == 'uvicorn.error.solvo.timing']
    assert sorted(r.stage for r in records) == sorted([
        'ollama_request', 'draft_extraction_total', 'ollama_request',
        'draft_extraction_total', 'audio_transcription', 'audio_extraction',
        'audio_draft_total',
    ])
    assert all(r.duration_ms >= 0 and r.outcome == 'success' for r in records)
    assert all(TEXT not in r.getMessage() and '3471234567' not in r.getMessage()
               for r in records)


def test_default_keep_alive(monkeypatch):
    from app.core.config import Settings
    monkeypatch.delenv('OLLAMA_KEEP_ALIVE', raising=False)
    assert Settings(_env_file=None).ollama_keep_alive == '30m'

    def handler(request):
        assert json.loads(request.content)['keep_alive'] == '30m'
        return response(RESULT)

    install_http(monkeypatch, handler)
    assert create_provider('ollama', model='test').extract(TEXT, []) == {
        **RESULT, 'warnings': [],
    }


def test_request_failure_still_records_duration(monkeypatch, caplog):
    def handler(request):
        assert request.extensions['timeout']['read'] == 7
        raise httpx.ReadTimeout('private request details', request=request)

    install_http(monkeypatch, handler)
    with caplog.at_level('INFO', logger='uvicorn.error.solvo.timing'):
        with pytest.raises(AIProviderUnavailableError, match='tempo di attesa'):
            create_provider('ollama', model='test', timeout=7).extract(TEXT, [])
    record = next(r for r in caplog.records if r.name == 'uvicorn.error.solvo.timing')
    assert record.stage == 'ollama_request'
    assert record.duration_ms >= 0
    assert record.outcome == 'error'
    assert 'private request details' not in record.getMessage()
