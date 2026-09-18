import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import event

from app.core.config import get_settings
from app.services.transcription import (
    InvalidAudioError, LocalWhisperTranscriptionProvider, MockTranscriptionProvider,
    NoSpeechError, TranscriptionUnavailableError, _local_provider,
    create_transcription_provider,
)


@pytest.fixture
def runtime(monkeypatch):
    streams = []
    waveform = [0.1, 0.2]
    def decode(source, sampling_rate):
        assert sampling_rate == 16000
        assert source.read() == b'actual webm bytes'
        streams.append(source)
        return waveform
    model = Mock()
    model.transcribe.side_effect = lambda *args, **kwargs: (
        iter([SimpleNamespace(text='  Guasto elettrico '), SimpleNamespace(text=' '),
              SimpleNamespace(text=' in Via Roma 12.  ')]), None
    )
    factory = Mock(return_value=model)
    fw = ModuleType('faster_whisper')
    fw.WhisperModel = factory
    audio = ModuleType('faster_whisper.audio')
    audio.decode_audio = Mock(side_effect=decode)
    ct = ModuleType('ctranslate2')
    ct.get_cuda_device_count = Mock(return_value=0)
    monkeypatch.setitem(sys.modules, 'faster_whisper', fw)
    monkeypatch.setitem(sys.modules, 'faster_whisper.audio', audio)
    monkeypatch.setitem(sys.modules, 'ctranslate2', ct)
    _local_provider.cache_clear()
    yield SimpleNamespace(model=model, factory=factory, decode=audio.decode_audio,
                          count=ct.get_cuda_device_count, streams=streams, waveform=waveform)
    _local_provider.cache_clear()


def test_selection_lazy_cache_actual_bytes_and_segments(runtime):
    assert isinstance(create_transcription_provider('mock', 'Demo'), MockTranscriptionProvider)
    assert create_transcription_provider('mock', 'Demo').transcribe(b'ignored', 'audio/webm') == 'Demo'
    provider = create_transcription_provider('local_whisper', 'ignored')
    assert isinstance(provider, LocalWhisperTranscriptionProvider)
    assert create_transcription_provider('local_whisper', 'other') is provider
    runtime.factory.assert_not_called()
    for _ in range(2):
        assert provider.transcribe(b'actual webm bytes', 'audio/webm') == 'Guasto elettrico in Via Roma 12.'
    runtime.factory.assert_called_once_with('small', device='cpu', compute_type='int8')
    runtime.model.transcribe.assert_called_with(runtime.waveform, language='it', vad_filter=True)
    assert all(stream.closed for stream in runtime.streams)


def test_language_and_explicit_cpu_compute(runtime):
    provider = create_transcription_provider('local_whisper', '', model_size='base', device='cpu', compute_type='float32', language='en')
    provider.transcribe(b'actual webm bytes', 'audio/wav')
    runtime.factory.assert_called_once_with('base', device='cpu', compute_type='float32')
    runtime.model.transcribe.assert_called_with(runtime.waveform, language='en', vad_filter=True)


def test_auto_cuda_initialization_falls_back_and_reuses_cpu(runtime):
    runtime.count.return_value = 1
    runtime.factory.side_effect = [RuntimeError('private cuda paths'), runtime.model]
    provider = LocalWhisperTranscriptionProvider()
    for _ in range(2):
        provider.transcribe(b'actual webm bytes', 'audio/webm')
    assert runtime.factory.call_count == 2
    assert runtime.factory.call_args_list[0].kwargs == {'device': 'cuda', 'compute_type': 'auto'}
    assert runtime.factory.call_args_list[1].kwargs == {'device': 'cpu', 'compute_type': 'int8'}


def test_auto_cuda_generator_failure_falls_back(runtime):
    runtime.count.return_value = 1
    cpu = Mock()
    cpu.transcribe.return_value = (iter([SimpleNamespace(text='CPU transcript')]), None)
    def failed_segments():
        yield SimpleNamespace(text='partial GPU result')
        raise RuntimeError('cuDNN not found')
    runtime.model.transcribe.return_value = (failed_segments(), None)
    runtime.model.transcribe.side_effect = None
    runtime.factory.side_effect = [runtime.model, cpu]
    provider = LocalWhisperTranscriptionProvider()
    assert provider.transcribe(b'actual webm bytes', 'audio/webm') == 'CPU transcript'
    assert provider._active_device == 'cpu'


def test_cuda_probe_failure_uses_cpu(runtime):
    runtime.count.side_effect = RuntimeError('driver unavailable')
    LocalWhisperTranscriptionProvider().transcribe(b'actual webm bytes', 'audio/webm')
    assert runtime.factory.call_args.kwargs['device'] == 'cpu'


def test_empty_recognition_and_stream_cleanup(runtime):
    runtime.model.transcribe.side_effect = None
    runtime.model.transcribe.return_value = (iter([SimpleNamespace(text='  ')]), None)
    with pytest.raises(NoSpeechError, match='Nessun parlato'):
        LocalWhisperTranscriptionProvider().transcribe(b'actual webm bytes', 'audio/webm')
    assert runtime.streams[0].closed


def test_decode_failure_closes_stream_and_does_not_load_model(runtime):
    streams = []
    def fail(source, **kwargs):
        streams.append(source)
        raise ValueError('private decoder details')
    runtime.decode.side_effect = fail
    with pytest.raises(InvalidAudioError, match='Audio non leggibile'):
        LocalWhisperTranscriptionProvider().transcribe(b'actual webm bytes', 'audio/webm')
    assert streams[0].closed
    runtime.factory.assert_not_called()


def test_missing_dependency_readable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, 'faster_whisper', None)
    with pytest.raises(TranscriptionUnavailableError, match='installazione'):
        LocalWhisperTranscriptionProvider().transcribe(b'audio', 'audio/webm')


def test_model_unavailable_and_invalid_configuration(runtime):
    runtime.factory.side_effect = RuntimeError('private download error')
    with pytest.raises(TranscriptionUnavailableError, match='Modello'):
        LocalWhisperTranscriptionProvider().transcribe(b'actual webm bytes', 'audio/webm')
    with pytest.raises(TranscriptionUnavailableError, match='Configurazione'):
        LocalWhisperTranscriptionProvider(device='invalid')
    with pytest.raises(TranscriptionUnavailableError, match='sconosciuto'):
        create_transcription_provider('unknown', '')
    with pytest.raises(InvalidAudioError, match='vuoto'):
        LocalWhisperTranscriptionProvider().transcribe(b'', 'audio/webm')


def test_local_endpoint_uses_existing_draft_pipeline_without_writes(api, runtime, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'ai_provider', 'mock')
    monkeypatch.setattr(settings, 'transcription_provider', 'local_whisper')
    for field, value in [('whisper_model_size', 'small'), ('whisper_device', 'auto'),
                         ('whisper_compute_type', 'auto'), ('whisper_language', 'it')]:
        monkeypatch.setattr(settings, field, value)
    client, engine = api
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda conn, cursor, statement, *args: statements.append(statement))
    response = client.post('/api/ai/work-order-draft-audio', files={'audio': ('recording.webm', b'actual webm bytes', 'audio/webm;codecs=opus')})
    assert response.status_code == 200
    data = response.json()
    assert data['transcript'] == 'Guasto elettrico in Via Roma 12.'
    assert data['transcription_source'] == 'local_whisper'
    assert data['draft']['category_id'] == 1
    assert data['draft']['fault_address'] == 'Via Roma 12'
    assert data['draft']['description'] == data['transcript']
    assert not any('simulata' in warning for warning in data['draft']['warnings'])
    assert statements and all(s.lstrip().upper().startswith('SELECT') for s in statements)
    assert client.get('/api/work-orders').json() == []


@pytest.mark.parametrize('failure,status,expected', [
    (NoSpeechError('Nessun parlato riconosciuto.'), 422, 'Nessun parlato'),
    (InvalidAudioError('Audio non leggibile.'), 422, 'Audio non leggibile'),
    (TranscriptionUnavailableError('Modello locale non disponibile.'), 503, 'Modello locale'),
])
def test_endpoint_provider_errors_are_readable(api, failure, status, expected):
    from app.api.ai import get_transcription_provider
    provider = Mock()
    provider.transcribe.side_effect = failure
    client, _ = api
    client.app.dependency_overrides[get_transcription_provider] = lambda: provider
    response = client.post('/api/ai/work-order-draft-audio', files={'audio': ('file.webm', b'audio', 'audio/webm')})
    assert response.status_code == status
    assert expected in response.json()['detail']


@pytest.mark.parametrize('mime', ['audio/webm', 'audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/mp4'])
def test_supported_containers_feed_real_bytes_to_decoder(runtime, mime):
    provider = LocalWhisperTranscriptionProvider()
    assert provider.transcribe(b'actual webm bytes', mime) == 'Guasto elettrico in Via Roma 12.'
    assert runtime.streams[0].closed


def test_empty_decoded_audio_does_not_load_model(runtime):
    runtime.decode.return_value = []
    runtime.decode.side_effect = None
    with pytest.raises(NoSpeechError):
        LocalWhisperTranscriptionProvider().transcribe(b'actual webm bytes', 'audio/webm')
    runtime.factory.assert_not_called()


def test_cpu_inference_failure_is_readable_and_stream_is_closed(runtime):
    runtime.model.transcribe.side_effect = RuntimeError('private runtime error')
    with pytest.raises(TranscriptionUnavailableError, match='Trascrizione locale non riuscita'):
        LocalWhisperTranscriptionProvider().transcribe(b'actual webm bytes', 'audio/webm')
    assert runtime.streams[0].closed
