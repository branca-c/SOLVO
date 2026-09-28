import json

import httpx
import pytest

from app.core.config import Settings
from app.domain.description_grounding import segment_source
from app.models import Category
from app.services.ai.groq import DEFAULT_GROQ_BASE_URL, DEFAULT_GROQ_MODEL, GroqAIProvider
from app.services.ai.provider import (
    AIProviderUnavailableError,
    InvalidAIOutputError,
    create_provider,
)
from app.services.work_order_drafts import build_draft


API_KEY = "gsk_test_secret_value"
TEXT = (
    "Sono Anna Bianchi, telefono 3471234567. Il guasto è in via Libertà 85. "
    "Il climatizzatore perde acqua e non raffredda."
)
RESULT = {
    "user_first_name": "Anna",
    "user_last_name": "Bianchi",
    "user_phone": "3471234567",
    "user_email": None,
    "fault_address": "Via Libertà 85",
    "category_name": "Climatizzazione",
    "priority": "MEDIA",
    "description": "Il climatizzatore perde acqua e non raffredda.",
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


def completion(data):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(data)}}]})


def groq_provider():
    return create_provider("groq", groq_api_key=API_KEY)


def test_factory_selects_groq_provider_and_config_defaults():
    provider = groq_provider()

    assert isinstance(provider, GroqAIProvider)
    assert provider.base_url == DEFAULT_GROQ_BASE_URL
    assert provider.model == DEFAULT_GROQ_MODEL
    settings = Settings(_env_file=None)
    assert settings.groq_base_url == DEFAULT_GROQ_BASE_URL
    assert settings.groq_model == DEFAULT_GROQ_MODEL
    assert settings.groq_timeout_seconds == 60


@pytest.mark.parametrize(("kwargs", "message"), [
    ({}, "GROQ_API_KEY"),
    ({"groq_api_key": " "}, "GROQ_API_KEY"),
    ({"groq_api_key": API_KEY, "groq_model": " "}, "GROQ_MODEL"),
    ({"groq_api_key": API_KEY, "groq_base_url": "file:///tmp/groq"}, "GROQ_BASE_URL"),
    ({"groq_api_key": API_KEY, "groq_timeout": 0}, "GROQ_TIMEOUT_SECONDS"),
])
def test_groq_configuration_is_validated_without_exposing_key(kwargs, message):
    with pytest.raises(AIProviderUnavailableError, match=message) as exc:
        create_provider("groq", **kwargs)

    assert API_KEY not in str(exc.value)


def test_groq_extract_draft_is_one_structured_generation_with_description(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        body = json.loads(request.content)
        assert API_KEY not in request.content.decode()
        assert body["model"] == "configured-groq-model"
        assert body["stream"] is False
        assert body["temperature"] == 0
        assert body["reasoning_effort"] == "low"
        assert body["response_format"]["type"] == "json_schema"
        schema = body["response_format"]["json_schema"]
        assert schema["name"] == "solvo_generated_work_order_draft"
        assert schema["strict"] is False
        assert schema["schema"]["properties"]["category_name"]["anyOf"][0]["enum"] == ["Climatizzazione"]
        assert "description" in schema["schema"]["properties"]
        assert "fault_quotes" not in json.dumps(body)
        assert body["messages"][1] == {"role": "user", "content": TEXT}
        return completion(RESULT)

    install_http(monkeypatch, handler)
    extraction = create_provider(
        "groq", groq_api_key=API_KEY, groq_model="configured-groq-model",
    ).extract_draft(TEXT, ["Climatizzazione"], segment_source(TEXT))

    assert len(requests) == 1
    assert extraction.description == RESULT["description"]
    assert extraction.structured == {key: value for key, value in RESULT.items() if key != "description"}
    assert extraction.fault_quotes is None


def test_groq_safe_description_is_retained_in_public_draft_with_one_request(monkeypatch):
    calls = []
    install_http(monkeypatch, lambda request: calls.append(request) or completion(RESULT))

    draft = build_draft(
        FakeSession([Category(id=7, name="Climatizzazione")]), TEXT, groq_provider(),
    )

    assert len(calls) == 1
    assert draft.description == RESULT["description"]
    assert draft.category_id == 7
    assert draft.priority.value == "MEDIA"


@pytest.mark.parametrize("unsafe_description", [
    "Anna Bianchi segnala il climatizzatore guasto.",
    "Il climatizzatore è guasto. Telefono 3471234567.",
    "Il climatizzatore è guasto. Email anna@example.com.",
])
def test_groq_requester_data_in_description_is_rejected_with_review_warning(
    monkeypatch, unsafe_description,
):
    result = {**RESULT, "user_email": "anna@example.com", "description": unsafe_description}
    install_http(monkeypatch, lambda request: completion(result))

    draft = build_draft(
        FakeSession([Category(id=7, name="Climatizzazione")]),
        TEXT.replace("Il guasto", "email anna@example.com. Il guasto"),
        groq_provider(),
    )

    assert draft.description == ""
    assert "Descrizione tecnica non individuata: completala prima di confermare." in draft.warnings
    assert draft.user_first_name == "Anna"
    assert draft.category_id == 7


def test_missing_groq_description_keeps_other_valid_fields(monkeypatch):
    result = dict(RESULT)
    result.pop("description")
    install_http(monkeypatch, lambda request: completion(result))

    draft = build_draft(
        FakeSession([Category(id=7, name="Climatizzazione")]), TEXT, groq_provider(),
    )

    assert draft.description == ""
    assert draft.user_first_name == "Anna"
    assert draft.category_id == 7
    assert draft.priority.value == "MEDIA"
    assert "Descrizione tecnica non individuata: completala prima di confermare." in draft.warnings


def test_groq_draft_keeps_existing_audio_email_reconciliation(monkeypatch):
    text = (
        "Telefono 3471234567, email anna.bianchi-gmail.com. "
        "Il climatizzatore perde acqua in via Libertà 85."
    )
    result = {
        **RESULT,
        "user_first_name": None,
        "user_last_name": None,
        "user_email": "anna.bianchi-gmail.com",
    }
    install_http(monkeypatch, lambda request: completion(result))

    draft = build_draft(
        FakeSession([Category(id=7, name="Climatizzazione")]), text, groq_provider(), audio=True,
    )

    assert draft.user_email == "anna.bianchi@gmail.com"
    assert any("Email ricostruita dalla trascrizione audio" in warning for warning in draft.warnings)
    assert draft.description == RESULT["description"]


def test_groq_output_keeps_deterministic_category_and_trapped_elevator_priority(monkeypatch):
    text = "Ci sono delle persone bloccate in ascensore nello stabile di via Roma 25."
    result = {
        "fault_address": "Via Roma 25",
        "category_name": "Non configurata",
        "priority": "MEDIA",
        "description": "Persone bloccate in ascensore.",
        "warnings": [],
    }
    install_http(monkeypatch, lambda request: completion(result))

    draft = build_draft(
        FakeSession([Category(id=3, name="Ascensore"), Category(id=4, name="Idraulico")]),
        text,
        groq_provider(),
    )

    assert draft.description == "Persone bloccate in ascensore."
    assert draft.category_name == "Ascensore"
    assert draft.priority.value == "URGENTE"


@pytest.mark.parametrize(("text", "description", "expected"), [
    (
        "Problemi di rete al PC del professor Pellitteri in via Roma 25.",
        "Problemi di rete al PC del professor Pellitteri.",
        "MEDIA",
    ),
    (
        "Blackout in via delle Alpi 45.",
        "Blackout segnalato.",
        "MEDIA",
    ),
    (
        "Blackout in tutto l'edificio in via delle Alpi 45.",
        "Blackout nell'edificio.",
        "ALTA",
    ),
])
def test_groq_active_fault_drafts_never_expose_null_priority(
    monkeypatch, text, description, expected,
):
    result = {
        "fault_address": "Via Roma 25",
        "category_name": "Rete",
        "priority": None,
        "description": description,
        "warnings": [],
    }
    install_http(monkeypatch, lambda request: completion(result))

    draft = build_draft(
        FakeSession([Category(id=8, name="Rete"), Category(id=9, name="Elettrico")]),
        text,
        groq_provider(),
    )

    assert draft.priority is not None
    assert draft.priority.value == expected


@pytest.mark.parametrize("reply", [
    httpx.Response(200, text="not JSON"),
    httpx.Response(200, json={}),
    httpx.Response(200, json={"choices": []}),
    completion({"priority": "CRITICA", "description": "x"}),
    completion({"category_id": 3, "description": "x"}),
])
def test_groq_malformed_json_and_invalid_schema_raise_controlled_error(monkeypatch, reply):
    install_http(monkeypatch, lambda request: reply)

    with pytest.raises(InvalidAIOutputError) as exc:
        groq_provider().extract_draft(TEXT, [], segment_source(TEXT))

    assert API_KEY not in str(exc.value)


@pytest.mark.parametrize(("failure", "message"), [
    ("connect", "non raggiungibile"),
    ("timeout", "scaduto"),
    (401, "non ha completato"),
    (500, "non ha completato"),
])
def test_groq_provider_failures_are_sanitized_and_do_not_log_secret(
    monkeypatch, caplog, failure, message,
):
    def handler(request):
        if failure == "connect":
            raise httpx.ConnectError(f"provider leaked {API_KEY}", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout(f"provider leaked {API_KEY}", request=request)
        return httpx.Response(failure, json={"error": f"provider leaked {API_KEY}"})

    install_http(monkeypatch, handler)
    with pytest.raises(AIProviderUnavailableError, match=message) as exc:
        groq_provider().extract_draft(TEXT, [], segment_source(TEXT))

    assert API_KEY not in str(exc.value)
    assert API_KEY not in caplog.text
