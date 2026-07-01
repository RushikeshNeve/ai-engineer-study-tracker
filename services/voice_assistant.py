from __future__ import annotations

from typing import Any

from services.speech_to_text import transcribe_audio_bytes
from services.text_to_speech import synthesize_speech


def transcribe_streamlit_audio(audio_value: Any) -> str:
    audio_bytes = audio_value.getvalue()
    filename = getattr(audio_value, "name", "recording.wav") or "recording.wav"
    return transcribe_audio_bytes(audio_bytes, filename)


def create_spoken_response(text: str) -> bytes:
    return synthesize_speech(text)
