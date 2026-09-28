"""Audio-only providers: no persistence or workflow access."""
from functools import lru_cache
from io import BytesIO
import math
from threading import Lock
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.services.timing import timed


DEFAULT_GROQ_TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"


class TranscriptionUnavailableError(Exception):
    pass


class InvalidAudioError(Exception):
    pass


class NoSpeechError(Exception):
    pass


CONTACT_TRANSCRIPTION_HINT = (
    "Dati di contatto: nelle email chiocciola significa @, punto significa ., "
    "underscore significa _. Trascrivi fedelmente numeri di telefono e indirizzi email."
)


class TranscriptionProvider(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> str: ...


class MockTranscriptionProvider:
    def __init__(self, text: str):
        self.text = text

    def transcribe(self, audio: bytes, content_type: str) -> str:
        return self.text


class GroqTranscriptionProvider:
    """Groq speech-to-text adapter; no persistence or text-draft generation."""

    def __init__(self, base_url: str, api_key: str,
                 model: str = DEFAULT_GROQ_TRANSCRIPTION_MODEL,
                 timeout: float = 60, language: str = "it"):
        if not api_key.strip():
            raise TranscriptionUnavailableError(
                "Configura GROQ_API_KEY quando TRANSCRIPTION_PROVIDER=groq."
            )
        if not model.strip():
            raise TranscriptionUnavailableError(
                "Configura GROQ_TRANSCRIPTION_MODEL quando TRANSCRIPTION_PROVIDER=groq."
            )
        try:
            parsed = urlsplit(base_url)
            parsed.port
        except ValueError as exc:
            raise TranscriptionUnavailableError(
                "GROQ_BASE_URL non valido: verifica host e porta."
            ) from exc
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise TranscriptionUnavailableError("GROQ_BASE_URL non valido: configura un URL HTTP/HTTPS.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise TranscriptionUnavailableError("GROQ_TIMEOUT_SECONDS deve essere un numero positivo finito.")
        if not language.strip():
            raise TranscriptionUnavailableError("Lingua della trascrizione Groq non valida.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout = timeout
        self.language = language.strip().lower()

    def transcribe(self, audio: bytes, content_type: str) -> str:
        if not audio:
            raise InvalidAudioError("Il file audio è vuoto.")
        filename = {
            "audio/webm": "recording.webm",
            "audio/wav": "recording.wav",
            "audio/x-wav": "recording.wav",
            "audio/mpeg": "recording.mp3",
            "audio/mp4": "recording.mp4",
        }.get(content_type, "recording")
        try:
            with timed("groq_transcription_request"), httpx.Client(
                timeout=self.timeout, trust_env=False,
            ) as client:
                response = client.post(
                    self.base_url + "/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={"model": self.model, "language": self.language},
                    files={"file": (filename, audio, content_type)},
                )
        except httpx.TimeoutException as exc:
            raise TranscriptionUnavailableError(
                "Groq: tempo di attesa della trascrizione scaduto. Riprova o usa il testo."
            ) from exc
        except httpx.RequestError as exc:
            raise TranscriptionUnavailableError(
                "Groq non raggiungibile. Verifica connessione e GROQ_BASE_URL."
            ) from exc
        if not response.is_success:
            raise TranscriptionUnavailableError(
                "Groq non ha completato la trascrizione. Verifica configurazione e disponibilità del provider."
            )
        try:
            transcript = response.json()["text"]
        except (ValueError, TypeError, KeyError) as exc:
            raise TranscriptionUnavailableError(
                "Risposta Groq di trascrizione non valida. Riprova o usa il testo."
            ) from exc
        if not isinstance(transcript, str) or not transcript.strip():
            raise TranscriptionUnavailableError(
                "Risposta Groq di trascrizione non valida. Riprova o usa il testo."
            )
        return transcript.strip()


class LocalWhisperTranscriptionProvider:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "auto", language: str = "it", beam_size: int = 3):
        self.model_size = model_size.strip()
        self.device = device.strip().lower()
        self.compute_type = compute_type.strip().lower()
        self.language = language.strip().lower()
        self.beam_size = beam_size
        if self.device not in {"auto", "cpu", "cuda"} or not all(
            (self.model_size, self.compute_type, self.language)
        ) or type(self.beam_size) is not int or self.beam_size < 1:
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
        segments, _ = self._model.transcribe(
            waveform, language=self.language, vad_filter=True,
            initial_prompt=CONTACT_TRANSCRIPTION_HINT,
            beam_size=self.beam_size,
        )
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
def _local_provider(model_size: str, device: str, compute_type: str, language: str, beam_size: int):
    return LocalWhisperTranscriptionProvider(model_size, device, compute_type, language, beam_size)


_provider_lock = Lock()


def create_transcription_provider(name: str, mock_text: str, *, model_size: str = "small",
                                  device: str = "auto", compute_type: str = "auto",
                                  language: str = "it", beam_size: int = 3,
                                  groq_api_key: str = "",
                                  groq_base_url: str = "https://api.groq.com/openai/v1",
                                  groq_model: str = DEFAULT_GROQ_TRANSCRIPTION_MODEL,
                                  groq_timeout: float = 60) -> TranscriptionProvider:
    selected = name.strip().casefold()
    if selected in {"mock", "fake"}:
        return MockTranscriptionProvider(mock_text)
    if selected in {"local", "local_whisper"}:
        with _provider_lock:
            return _local_provider(model_size, device, compute_type, language, beam_size)
    if selected == "groq":
        return GroqTranscriptionProvider(
            groq_base_url, groq_api_key, groq_model, groq_timeout, language,
        )
    raise TranscriptionUnavailableError("Provider di trascrizione sconosciuto. Usa mock, local_whisper o groq.")
