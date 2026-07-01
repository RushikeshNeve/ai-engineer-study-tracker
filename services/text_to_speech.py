from __future__ import annotations

import os

from openai import OpenAI


DEFAULT_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
FALLBACK_TTS_MODEL = "tts-1"
DEFAULT_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx")


def synthesize_speech(
    text: str,
    model: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
) -> bytes:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OpenAI API key not found.")
    if not text.strip():
        raise RuntimeError("No text received for speech synthesis.")

    client = OpenAI()
    selected_model = model or DEFAULT_TTS_MODEL
    selected_voice = voice or DEFAULT_TTS_VOICE
    selected_speed = float(speed if speed is not None else 0.95)
    try:
        response = client.audio.speech.create(
            model=selected_model,
            voice=selected_voice,
            input=text,
            speed=selected_speed,
        )
    except Exception:
        if selected_model == FALLBACK_TTS_MODEL:
            raise
        response = client.audio.speech.create(
            model=FALLBACK_TTS_MODEL,
            voice=selected_voice,
            input=text,
            speed=selected_speed,
        )
    if hasattr(response, "read"):
        return response.read()
    content = getattr(response, "content", None)
    if content:
        return content
    return bytes(response)
