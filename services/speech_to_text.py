from __future__ import annotations

import io
import os

from openai import OpenAI


DEFAULT_TRANSCRIPTION_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
FALLBACK_TRANSCRIPTION_MODEL = "whisper-1"


def transcribe_audio(audio_file_path: str, model: str | None = None) -> str:
    with open(audio_file_path, "rb") as audio_file:
        audio_file.name = audio_file_path
        return _transcribe_file(audio_file, model or DEFAULT_TRANSCRIPTION_MODEL)


def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "recording.wav", model: str | None = None) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OpenAI API key not found.")
    if not audio_bytes:
        raise RuntimeError("No audio data received.")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename or "recording.wav"
    return _transcribe_file(audio_file, model or DEFAULT_TRANSCRIPTION_MODEL)


def _transcribe_file(audio_file, model: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OpenAI API key not found.")
    client = OpenAI()
    try:
        response = client.audio.transcriptions.create(model=model, file=audio_file)
    except Exception:
        if model == FALLBACK_TRANSCRIPTION_MODEL:
            raise
        audio_file.seek(0)
        response = client.audio.transcriptions.create(model=FALLBACK_TRANSCRIPTION_MODEL, file=audio_file)
    transcript = getattr(response, "text", "") or ""
    return transcript.strip()
