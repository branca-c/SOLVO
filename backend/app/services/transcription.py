"""Audio-only providers: no persistence or workflow access."""
from functools import lru_cache
from io import BytesIO
from threading import Lock
from typing import Protocol


class TranscriptionUnavailableError(Exception):
    pass


class InvalidAudioError(Exception):
    pass


class NoSpeechError(Exception):
    pass


class TranscriptionProvider(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> str: ...


class MockTranscriptionProvider:
    def __init__(self, text: str):
        self.text = text

    def transcribe(self, audio: bytes, content_type: str) -> str:
        return self.text


class LocalWhisperTranscriptionProvider:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "auto", language: str = "it"):
        self.model_size = model_size.strip()
        self.device = device.strip().lower()
        self.compute_type = compute_type.strip().lower()
        self.language = language.strip().lower()
        if self.device not in {"auto", "cpu", "cuda"} or not all(
            (self.model_size, self.compute_type, self.language)
        ):
            raise TranscriptionUnavailableError("Configurazione della trascrizione locale non valida.")
        self._model = None
        self._active_device = None
        # Serialize loading/inference so parallel requests reuse one model safely.
        self._lock = Lock()

    def _initialize(self, model_class, device: str):
        compute = "int8" if device == "cpu" and (
            self.compute_type == "auto" or self.device == "auto"
        ) else self.compute_type
        try:
            model = model_class(self.model_size, device=device, compute_type=compute)
        except Exception as exc:
            raise TranscriptionUnavailableError(
                "Modello di trascrizione locale non disponibile. Verifica il modello, "
                "il download iniziale e la configurazione del dispositivo."
            ) from exc
        self._model = model
        self._active_device = device

    def _load_model(self, model_class, cuda_count):
        if self._model is not None:
            return
        device = self.device
        if device == "auto":
            try:
                device = "cuda" if cuda_count() > 0 else "cpu"
            except Exception:
                device = "cpu"
        try:
            self._initialize(model_class, device)
        except TranscriptionUnavailableError:
            if self.device != "auto" or device != "cuda":
                raise
            self._initialize(model_class, "cpu")

    def _recognize(self, waveform) -> str:
        segments, _ = self._model.transcribe(waveform, language=self.language, vad_filter=True)
        # faster-whisper performs inference when the segment generator is consumed.
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()

    def transcribe(self, audio: bytes, content_type: str) -> str:
        if not audio:
            raise InvalidAudioError("Il file audio è vuoto.")
        try:
            from faster_whisper import WhisperModel
            from faster_whisper.audio import decode_audio
            from ctranslate2 import get_cuda_device_count
        except Exception as exc:
            raise TranscriptionUnavailableError(
                "Trascrizione locale non inizializzabile. Verifica l’installazione "
                "di faster-whisper e delle sue dipendenze."
            ) from exc
        # PyAV decodes WebM/Opus, WAV, MPEG and MP4 supported by its bundled codecs.
        # No audio file is written; the byte stream closes on success and failure.
        with BytesIO(audio) as source:
            try:
                waveform = decode_audio(source, sampling_rate=16000)
            except Exception as exc:
                raise InvalidAudioError("Audio non leggibile o formato non supportato. Prova un altro file.") from exc
        if len(waveform) == 0:
            raise NoSpeechError("Nessun parlato riconosciuto. Registra di nuovo o usa il testo.")
        with self._lock:
            self._load_model(WhisperModel, get_cuda_device_count)
            try:
                transcript = self._recognize(waveform)
            except Exception as exc:
                if self.device == "auto" and self._active_device == "cuda":
                    self._model = None
                    self._initialize(WhisperModel, "cpu")
                    try:
                        transcript = self._recognize(waveform)
                    except Exception as cpu_exc:
                        raise TranscriptionUnavailableError("Trascrizione locale non riuscita. Riprova o usa il testo.") from cpu_exc
                else:
                    raise TranscriptionUnavailableError("Trascrizione locale non riuscita. Riprova o usa il testo.") from exc
        if not transcript:
            raise NoSpeechError("Nessun parlato riconosciuto. Registra di nuovo o usa il testo.")
        return transcript


@lru_cache(maxsize=4)
def _local_provider(model_size: str, device: str, compute_type: str, language: str):
    return LocalWhisperTranscriptionProvider(model_size, device, compute_type, language)


_provider_lock = Lock()


def create_transcription_provider(name: str, mock_text: str, *, model_size: str = "small",
                                  device: str = "auto", compute_type: str = "auto",
                                  language: str = "it") -> TranscriptionProvider:
    selected = name.strip().casefold()
    if selected in {"mock", "fake"}:
        return MockTranscriptionProvider(mock_text)
    if selected == "local_whisper":
        with _provider_lock:
            return _local_provider(model_size, device, compute_type, language)
    raise TranscriptionUnavailableError("Provider di trascrizione sconosciuto. Usa mock o local_whisper.")
