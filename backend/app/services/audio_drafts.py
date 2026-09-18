from typing import BinaryIO

from sqlalchemy.orm import Session

from app.services.timing import timed
from app.schemas.work_order_draft import AudioWorkOrderDraft
from app.services.ai.provider import AIProvider
from app.services.transcription import (
    InvalidAudioError, NoSpeechError, MockTranscriptionProvider,
    LocalWhisperTranscriptionProvider, TranscriptionProvider, TranscriptionUnavailableError,
)
from app.services.work_order_drafts import build_draft


class AudioDraftError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def build_audio_draft(
    audio: BinaryIO, content_type: str | None, db: Session,
    provider: AIProvider, transcription: TranscriptionProvider, max_mb: int,
) -> AudioWorkOrderDraft:
    with timed("audio_draft_total"):
        mime = (content_type or "").split(";", 1)[0].strip().lower()
        if mime not in {"audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4"}:
            raise AudioDraftError(415, "Formato audio non supportato.")
        limit = max_mb * 1024 * 1024
        content = audio.read(limit + 1)
        if len(content) > limit:
            raise AudioDraftError(413, f"Audio troppo grande: massimo {max_mb} MiB.")
        if not content:
            raise AudioDraftError(422, "Il file audio è vuoto.")
        try:
            with timed("audio_transcription"):
                transcript = transcription.transcribe(content, mime)
        except (InvalidAudioError, NoSpeechError) as exc:
            raise AudioDraftError(422, str(exc)) from exc
        except TranscriptionUnavailableError as exc:
            raise AudioDraftError(503, str(exc)) from exc
        except Exception as exc:
            raise AudioDraftError(503, "Trascrizione non disponibile. Riprova o usa il testo.") from exc
        if not isinstance(transcript, str) or not transcript.strip() or len(transcript) > 10000:
            raise AudioDraftError(422, "Trascrizione vuota o troppo lunga (massimo 10000 caratteri).")
        transcript = transcript.strip()
        with timed("audio_extraction"):
            draft = build_draft(db, transcript, provider)
        if isinstance(transcription, MockTranscriptionProvider):
            draft.warnings = ["Trascrizione simulata: testo dimostrativo, non riconosciuto dall’audio.", *draft.warnings][:10]
        source = "mock" if isinstance(transcription, MockTranscriptionProvider) else (
            "local_whisper" if isinstance(transcription, LocalWhisperTranscriptionProvider) else None
        )
        return AudioWorkOrderDraft(transcript=transcript, draft=draft, transcription_source=source)
