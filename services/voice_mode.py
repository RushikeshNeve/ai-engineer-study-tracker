from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.speech_to_text import transcribe_audio_bytes
from services.text_to_speech import synthesize_speech


DB_PATH = Path("study_tracker.db")
AUDIO_DIR = Path("voice_audio")

DEFAULT_VOICE_SETTINGS = {
    "voice_name": "onyx",
    "tts_model": "gpt-4o-mini-tts",
    "stt_model": "gpt-4o-mini-transcribe",
    "speaking_speed": 0.95,
    "response_style": "concise",
    "autoplay_enabled": 1,
    "transcript_confirmation_enabled": 1,
    "save_audio_history_enabled": 1,
    "startup_greeting_enabled": 1,
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_voice_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS voice_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voice_name TEXT,
                tts_model TEXT,
                stt_model TEXT,
                speaking_speed REAL DEFAULT 0.95,
                response_style TEXT,
                autoplay_enabled INTEGER DEFAULT 1,
                transcript_confirmation_enabled INTEGER DEFAULT 1,
                save_audio_history_enabled INTEGER DEFAULT 1,
                startup_greeting_enabled INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS voice_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_transcript TEXT,
                assistant_response TEXT,
                audio_file_path TEXT,
                stt_model TEXT,
                tts_model TEXT,
                voice_name TEXT,
                created_at TEXT
            );
            """
        )
        ensure_voice_conversation_columns(conn)
        existing = conn.execute("SELECT id FROM voice_settings ORDER BY id LIMIT 1").fetchone()
        if not existing:
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO voice_settings (
                    voice_name, tts_model, stt_model, speaking_speed,
                    response_style, autoplay_enabled, transcript_confirmation_enabled,
                    save_audio_history_enabled, startup_greeting_enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_VOICE_SETTINGS["voice_name"],
                    DEFAULT_VOICE_SETTINGS["tts_model"],
                    DEFAULT_VOICE_SETTINGS["stt_model"],
                    DEFAULT_VOICE_SETTINGS["speaking_speed"],
                    DEFAULT_VOICE_SETTINGS["response_style"],
                    DEFAULT_VOICE_SETTINGS["autoplay_enabled"],
                    DEFAULT_VOICE_SETTINGS["transcript_confirmation_enabled"],
                    DEFAULT_VOICE_SETTINGS["save_audio_history_enabled"],
                    DEFAULT_VOICE_SETTINGS["startup_greeting_enabled"],
                    now,
                    now,
                ),
            )


def ensure_voice_conversation_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(voice_conversations)").fetchall()}
    migrations = {
        "audio_file_path": "ALTER TABLE voice_conversations ADD COLUMN audio_file_path TEXT",
        "stt_model": "ALTER TABLE voice_conversations ADD COLUMN stt_model TEXT",
        "tts_model": "ALTER TABLE voice_conversations ADD COLUMN tts_model TEXT",
        "voice_name": "ALTER TABLE voice_conversations ADD COLUMN voice_name TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            conn.execute(sql)


def get_voice_settings() -> dict[str, Any]:
    initialize_voice_tables()
    with connect() as conn:
        row = conn.execute("SELECT * FROM voice_settings ORDER BY id LIMIT 1").fetchone()
    settings = dict(row) if row else {}
    for key, value in DEFAULT_VOICE_SETTINGS.items():
        settings.setdefault(key, value)
    return settings


def update_voice_settings(settings: dict[str, Any]) -> dict[str, Any]:
    initialize_voice_tables()
    current = get_voice_settings()
    row_id = int(current.get("id", 1))
    values = {
        "voice_name": settings.get("voice_name", current.get("voice_name", "onyx")),
        "tts_model": settings.get("tts_model", current.get("tts_model", "gpt-4o-mini-tts")),
        "stt_model": settings.get("stt_model", current.get("stt_model", "gpt-4o-mini-transcribe")),
        "speaking_speed": float(settings.get("speaking_speed", current.get("speaking_speed", 0.95)) or 0.95),
        "response_style": settings.get("response_style", current.get("response_style", "concise")),
        "autoplay_enabled": int(bool(settings.get("autoplay_enabled", current.get("autoplay_enabled", 1)))),
        "transcript_confirmation_enabled": int(bool(settings.get("transcript_confirmation_enabled", current.get("transcript_confirmation_enabled", 1)))),
        "save_audio_history_enabled": int(bool(settings.get("save_audio_history_enabled", current.get("save_audio_history_enabled", 1)))),
        "startup_greeting_enabled": int(bool(settings.get("startup_greeting_enabled", current.get("startup_greeting_enabled", 1)))),
    }
    with connect() as conn:
        conn.execute(
            """
            UPDATE voice_settings
            SET voice_name = ?, tts_model = ?, stt_model = ?, speaking_speed = ?,
                response_style = ?, autoplay_enabled = ?, transcript_confirmation_enabled = ?,
                save_audio_history_enabled = ?, startup_greeting_enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                values["voice_name"],
                values["tts_model"],
                values["stt_model"],
                values["speaking_speed"],
                values["response_style"],
                values["autoplay_enabled"],
                values["transcript_confirmation_enabled"],
                values["save_audio_history_enabled"],
                values["startup_greeting_enabled"],
                datetime.now().isoformat(),
                row_id,
            ),
        )
    return {"updated": True, "voice_settings_id": row_id}


def transcribe_streamlit_audio(audio_value: Any, model: str | None = None) -> str:
    audio_bytes = audio_value.getvalue()
    filename = getattr(audio_value, "name", "recording.wav") or "recording.wav"
    return transcribe_audio_bytes(audio_bytes, filename, model=model)


def handle_voice_input(audio_value: Any, settings: dict[str, Any] | None = None) -> str:
    active_settings = settings or get_voice_settings()
    return transcribe_streamlit_audio(audio_value, active_settings.get("stt_model"))


def create_spoken_response(
    text: str,
    model: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
) -> bytes:
    return synthesize_speech(text, model=model, voice=voice, speed=speed)


def generate_voice_response(text: str, settings: dict[str, Any] | None = None) -> bytes:
    active_settings = settings or get_voice_settings()
    return create_spoken_response(
        text,
        model=active_settings.get("tts_model"),
        voice=active_settings.get("voice_name"),
        speed=float(active_settings.get("speaking_speed", 0.95) or 0.95),
    )


def save_audio_response(audio_bytes: bytes, suffix: str = ".mp3") -> str:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIO_DIR / f"mythos_response_{uuid4().hex}{suffix}"
    path.write_bytes(audio_bytes)
    return str(path)


def save_voice_conversation(
    user_transcript: str,
    assistant_response: str,
    audio_file_path: str = "",
    stt_model: str = "",
    tts_model: str = "",
    voice_name: str = "",
) -> dict[str, Any]:
    initialize_voice_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO voice_conversations (
                user_transcript, assistant_response, audio_file_path,
                stt_model, tts_model, voice_name, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_transcript,
                assistant_response,
                audio_file_path,
                stt_model,
                tts_model,
                voice_name,
                datetime.now().isoformat(),
            ),
        )
    return {"saved": True, "voice_conversation_id": cursor.lastrowid}
