import pytest

from app.api.ai import get_ai_provider, get_transcription_provider
from app.domain.email_addresses import audio_email_candidate, valid_email
from app.services.transcription import MockTranscriptionProvider
from app.services.work_order_drafts import _grounded
from tests.test_work_order_drafts import StubProvider
from tests.test_ollama import install_http, response
from app.services.ai.ollama import OllamaAIProvider


@pytest.mark.parametrize("text,expected", [
    ("la mia mail è chiara punto branca 1991 chiocciola gmail punto com", "chiara.branca1991@gmail.com"),
    ("Il mio indirizzo e-mail è chiara.branca1991-gmail.com", "chiara.branca1991@gmail.com"),
    ("email: Chiara.branca1991@gmail.com", "Chiara.branca1991@gmail.com"),
    ("mail: chiara underscore branca at gmail punto com", "chiara_branca@gmail.com"),
    ("chiara.branca1991-gmail.com", None),
    ("Il tubo perde nel punto nord-est", None),
    ("email: chiara-branca-gmail.com", None),
    ("email: chiara--gmail.com", None),
    ("email: chiara.branca1991-gmail", None),
    ("email: chiara@gmail.com e-mail: altra@gmail.com", None),
    ("email: chiara@@gmail.com", None),
    ("email: chiara@gmail..com", None),
    ("email: chiara@gmail.com..altro", None),
    ("email: chiara at gmail punto com punto", None),
    ("email è chiarapuntobranca1991 chiocciolaggmail.com", "chiara.branca1991@gmail.com"),
    ("email è chiarapuntobranca1991chiocciolagmailpuntocom", "chiara.branca1991@gmail.com"),
    ("email è mariorossiunderscoretestchiocciolagmail.com", "mariorossi_test@gmail.com"),
    ("email è chiarapunto branca1991chiocciola gmail.com", "chiara.branca1991@gmail.com"),
    ("email è chiaraatgmailpuntocom", "chiara@gmail.com"),
    ("email è chiaraat gmail.com", "chiara@gmail.com"),
    ("email è chiara atgmail.com", "chiara@gmail.com"),
    ("email è chiara at gmail.com", "chiara@gmail.com"),
    ("email è katiaatgmail.com", None),
    ("email è chiarapuntobranca1991 chiocciolaazienda-esempioo.it", "chiara.branca1991@azienda-esempioo.it"),
    ("email è chiarapuntobranca1991 chiocciola", None),
    ("email è chiarapuntobranca1991 chiocciolaggmail..com", None),
    ("email è chiarapuntobranca1991@gmail.com", "chiarapuntobranca1991@gmail.com"),
    ("Nel chiarapuntobranca il tubo perde", None),
])
def test_bounded_audio_email(text, expected):
    assert audio_email_candidate(text) == expected


@pytest.mark.parametrize("separator,symbol", [("punto", "."), ("underscore", "_")])
@pytest.mark.parametrize("before,after", [(" ", " "), ("", " "), (" ", ""), ("", "")])
def test_separator_attachment_positions(separator, symbol, before, after):
    transcript = f"email: mario{before}{separator}{after}rossi chiocciolagmail.com"
    assert audio_email_candidate(transcript) == f"mario{symbol}rossi@gmail.com"


@pytest.mark.parametrize("before,after", [(" ", " "), ("", " "), (" ", ""), ("", "")])
def test_chiocciola_attachment_positions(before, after):
    assert audio_email_candidate(f"email: mario{before}chiocciola{after}gmail.com") == "mario@gmail.com"


@pytest.mark.parametrize("domain,expected", [
    ("ggmail.com", "gmail.com"), ("gmai.com", "gmail.com"),
    ("gmaik.com", "gmail.com"), ("gmial.com", "gmial.com"),
    ("azienda-esempioo.it", "azienda-esempioo.it"),
])
def test_unique_one_edit_domain_only(domain, expected):
    assert audio_email_candidate(f"email: chiara chiocciola{domain}") == f"chiara@{expected}"


@pytest.mark.parametrize("value", ["a..b@gmail.com", ".a@gmail.com", "a@-gmail.com", "a@gmail", "a@gmail..com", "a b@gmail.com", "chiara.branca1991-gmail.com"])
def test_email_syntax_rejects_invalid_values(value):
    assert not valid_email(value)


def test_email_grounding_preserves_punctuation_and_boundaries():
    assert _grounded("user_email", "chiara.branca1991@gmail.com", "Email: chiara.branca1991@gmail.com.")
    assert not _grounded("user_email", "chiara.branca1991@gmail.com", "Email: chiara.branca1991-gmail.com")
    assert not _grounded("user_email", "a@gmail.com", "Email: altra.a@gmail.com")
    assert not _grounded("user_email", "a_b@gmail.com", "Email: a-b@gmail.com")


@pytest.mark.parametrize("transcript,expected", [
    ("la mia mail è chiara punto branca 1991 chiocciola gmail punto com", "chiara.branca1991@gmail.com"),
    ("indirizzo e-mail è chiara.branca1991-gmail.com", "chiara.branca1991@gmail.com"),
    ("email: chiara.branca1991@gmail.com", "chiara.branca1991@gmail.com"),
    ("chiara.branca1991-gmail.com", None),
    ("email: chiara-branca-gmail.com", None),
    ("Sono Chiara Branca. Il mio indirizzo email è\nchiarapuntobranca1991 chiocciolaggmail.com. Grazie.", "chiara.branca1991@gmail.com"),
    ("email è chiarapuntobranca1991chiocciolagmailpuntocom", "chiara.branca1991@gmail.com"),
    ("email è chiarapuntobranca1991 chiocciola", None),
])
def test_audio_reconciles_after_real_ollama_validation(api, monkeypatch, transcript, expected):
    client, _ = api
    transcript += "; telefono 333 1234567; il tubo perde acqua."
    def handler(request):
        import json
        assert json.loads(request.content)["messages"][1]["content"] == transcript
        return response({"user_email": "chiara.branca1991-gmail.com", "user_phone": "3331234567", "description": "Perdita dal tubo"})
    install_http(monkeypatch, handler)
    client.app.dependency_overrides[get_ai_provider] = lambda: OllamaAIProvider("http://localhost:11434", "unchanged", 30)
    client.app.dependency_overrides[get_transcription_provider] = lambda: MockTranscriptionProvider(transcript)
    result = client.post("/api/ai/work-order-draft-audio", files={"audio": ("a.webm", b"audio", "audio/webm")})
    assert result.status_code == 200
    assert result.json()["transcript"] == transcript
    draft = result.json()["draft"]
    assert draft["user_email"] == expected
    assert draft["user_phone"] == "3331234567"
    assert draft["warnings"]


@pytest.mark.parametrize("text,email,expected", [
    ("mail: chiara.branca1991-gmail.com", "chiara.branca1991-gmail.com", None),
    ("mail: chiara punto branca 1991 chiocciola gmail punto com", "chiara.branca1991@gmail.com", None),
    ("mail: chiara.branca1991@gmail.com", "chiara.branca1991@gmail.com", "chiara.branca1991@gmail.com"),
    ("mail: chiara.branca1991-gmail.com", "chiara.branca1991@gmail.com", None),
    ("email è chiarapuntobranca1991 chiocciolaggmail.com", "chiara.branca1991@gmail.com", None),
    ("email è chiara@ggmail.com", "chiara@ggmail.com", "chiara@ggmail.com"),
])
def test_text_never_uses_audio_repair(api, text, email, expected):
    client, _ = api
    client.app.dependency_overrides[get_ai_provider] = lambda: StubProvider({"user_email": email, "description": "Perdita"})
    result = client.post("/api/ai/work-order-draft", json={"text": text})
    assert result.status_code == 200
    assert result.json()["user_email"] == expected


def test_ambiguous_allowlist_domain_is_rejected(monkeypatch):
    from app.domain import email_addresses
    monkeypatch.setattr(email_addresses, "COMMON_EMAIL_DOMAINS", ("gmail.com", "gmaim.com"))
    assert audio_email_candidate("email: chiara chiocciolagmaii.com") is None


def test_domain_correction_warns_even_when_ai_already_correct(api):
    client, _ = api
    transcript = "email è chiarapuntobranca1991 chiocciolaggmail.com"
    client.app.dependency_overrides[get_ai_provider] = lambda: StubProvider({"user_email": "chiara.branca1991@gmail.com"})
    client.app.dependency_overrides[get_transcription_provider] = lambda: MockTranscriptionProvider(transcript)
    result = client.post("/api/ai/work-order-draft-audio", files={"audio": ("a.webm", b"audio", "audio/webm")})
    assert result.status_code == 200
    assert result.json()["draft"]["user_email"] == "chiara.branca1991@gmail.com"
    assert any("Email ricostruita" in w for w in result.json()["draft"]["warnings"])
