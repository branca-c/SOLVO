import pytest
from sqlalchemy import event

from app.api.ai import get_transcription_provider
from app.core.config import get_settings

URL = '/api/ai/work-order-draft-audio'


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'ai_provider', 'mock')
    monkeypatch.setattr(settings, 'transcription_provider', 'mock')
    monkeypatch.setattr(settings, 'transcription_mock_text', 'Perdita di acqua dal tubo del bagno.')


@pytest.mark.parametrize('mime', ['audio/webm', 'audio/webm;codecs=opus', 'audio/wav', 'audio/mpeg', 'audio/mp4'])
def test_audio_mock_uses_draft_pipeline_without_writes(api, mime):
    client, engine = api
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda conn, cursor, statement, *args: statements.append(statement))
    response = client.post(URL, files={'audio': ('sample', b'demo audio', mime)})
    assert response.status_code == 200
    data = response.json()
    assert data['transcript'] == 'Perdita di acqua dal tubo del bagno.'
    assert data['draft']['description'] == data['transcript']
    assert data['draft']['category_id'] == 2
    assert data['draft']['user_phone'] is None
    assert 'simulata' in data['draft']['warnings'][0]
    assert statements and all(s.lstrip().upper().startswith('SELECT') for s in statements)


@pytest.mark.parametrize('content,mime,status', [(b'', 'audio/wav', 422), (b'a', 'text/plain', 415), (b'a' * (10 * 1024 * 1024 + 1), 'audio/webm', 413)])
def test_invalid_upload(api, content, mime, status):
    client, _ = api
    assert client.post(URL, files={'audio': ('file', content, mime)}).status_code == status


def test_missing_upload(api):
    assert api[0].post(URL).status_code == 422


@pytest.mark.parametrize('text', ['', '   ', 'a' * 10001, None])
def test_invalid_transcript(api, text):
    class Stub:
        def transcribe(self, audio, content_type):
            return text
    client, _ = api
    client.app.dependency_overrides[get_transcription_provider] = lambda: Stub()
    assert client.post(URL, files={'audio': ('file.wav', b'a', 'audio/wav')}).status_code == 422


def test_transcription_failure_sanitized(api):
    class Stub:
        def transcribe(self, audio, content_type):
            raise RuntimeError('private provider information')
    client, _ = api
    client.app.dependency_overrides[get_transcription_provider] = lambda: Stub()
    response = client.post(URL, files={'audio': ('file.wav', b'a', 'audio/wav')})
    assert response.status_code == 503
    assert 'private' not in response.text


def test_unknown_provider(api, monkeypatch):
    monkeypatch.setattr(get_settings(), 'transcription_provider', 'unknown')
    assert api[0].post(URL, files={'audio': ('file.wav', b'a', 'audio/wav')}).status_code == 503


def test_injected_transcript_resolves_configured_category(api):
    class Stub:
        def transcribe(self, audio, content_type):
            assert audio == b'example'
            assert content_type == 'audio/webm'
            return 'Guasto elettrico in Via Roma 12.'
    client, _ = api
    client.app.dependency_overrides[get_transcription_provider] = lambda: Stub()
    response = client.post(URL, files={'audio': ('file', b'example', 'audio/webm;codecs=opus')})
    assert response.status_code == 200
    assert response.json()['draft']['category_id'] == 1
    assert response.json()['draft']['fault_address'] == 'Via Roma 12'


@pytest.mark.parametrize('content', [b'audio', b''])
def test_upload_closed_on_success_and_failure(api, monkeypatch, content):
    from starlette.datastructures import UploadFile
    original = UploadFile.close
    closed = []

    async def close(upload):
        await original(upload)
        closed.append(upload.file.closed)

    monkeypatch.setattr(UploadFile, 'close', close)
    api[0].post(URL, files={'audio': ('file.wav', content, 'audio/wav')})
    assert closed and all(closed)
