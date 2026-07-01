from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from services.observability_service import log_memory_retrieval


DB_PATH = Path("study_tracker.db")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_memory_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT,
                content TEXT NOT NULL,
                source TEXT,
                importance INTEGER DEFAULT 1,
                pinned INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER,
                embedding_model TEXT,
                embedding_json TEXT,
                created_at TEXT,
                FOREIGN KEY(memory_id) REFERENCES user_memories(id)
            );
            """
        )


def create_embedding(text: str) -> list[float]:
    if not os.getenv("OPENAI_API_KEY"):
        return []
    client = OpenAI()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def save_memory(
    content: str,
    memory_type: str = "fact",
    source: str = "mythos",
    importance: int = 1,
    pinned: bool = False,
) -> dict[str, Any]:
    initialize_memory_tables()
    clean_content = content.strip()
    if not clean_content:
        return {"saved": False, "reason": "empty memory"}

    now = datetime.now().isoformat()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM user_memories WHERE lower(content) = lower(?) LIMIT 1",
            (clean_content,),
        ).fetchone()
        if existing:
            return {"saved": False, "memory_id": existing["id"], "reason": "duplicate"}
        cursor = conn.execute(
            """
            INSERT INTO user_memories (
                memory_type, content, source, importance, pinned, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_type, clean_content, source, importance, int(pinned), now, now),
        )
        memory_id = cursor.lastrowid

    embedding = create_embedding(clean_content)
    if embedding:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_embeddings (
                    memory_id, embedding_model, embedding_json, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (memory_id, EMBEDDING_MODEL, json.dumps(embedding), now),
            )
    return {"saved": True, "memory_id": memory_id}


def keyword_score(query: str, content: str) -> float:
    query_terms = {term for term in re.split(r"[^a-z0-9+#.]+", query.lower()) if len(term) > 2}
    content_lower = content.lower()
    if not query_terms:
        return 0.0
    return sum(1 for term in query_terms if term in content_lower) / len(query_terms)


def search_memory(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    initialize_memory_tables()
    query_embedding = create_embedding(query)
    with connect() as conn:
        memories = [dict(row) for row in conn.execute("SELECT * FROM user_memories").fetchall()]
        embeddings = {
            row["memory_id"]: json.loads(row["embedding_json"])
            for row in conn.execute("SELECT memory_id, embedding_json FROM memory_embeddings").fetchall()
            if row["embedding_json"]
        }

    scored = []
    for memory in memories:
        semantic = cosine_similarity(query_embedding, embeddings.get(memory["id"], [])) if query_embedding else 0.0
        lexical = keyword_score(query, memory["content"])
        pinned_boost = 0.15 if memory.get("pinned") else 0
        importance_boost = min(float(memory.get("importance") or 1), 5) * 0.03
        score = semantic or lexical
        score += pinned_boost + importance_boost
        if score > 0 or memory.get("pinned"):
            memory["score"] = round(score, 4)
            scored.append(memory)
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def retrieve_context(query: str, top_k: int = 5) -> str:
    started = time.perf_counter()
    memories = search_memory(query, top_k)
    log_memory_retrieval(query, len(memories), int((time.perf_counter() - started) * 1000))
    if not memories:
        return ""
    lines = ["Relevant long-term Mythos memory:"]
    for memory in memories:
        marker = "pinned" if memory.get("pinned") else memory.get("memory_type", "memory")
        lines.append(f"- [{marker}] {memory['content']}")
    return "\n".join(lines)


def update_memory(
    memory_id: int,
    content: str,
    memory_type: str,
    source: str,
    importance: int,
    pinned: bool,
) -> dict[str, Any]:
    initialize_memory_tables()
    now = datetime.now().isoformat()
    with connect() as conn:
        conn.execute(
            """
            UPDATE user_memories
            SET content = ?, memory_type = ?, source = ?, importance = ?,
                pinned = ?, updated_at = ?
            WHERE id = ?
            """,
            (content, memory_type, source, importance, int(pinned), now, memory_id),
        )
        conn.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
    embedding = create_embedding(content)
    if embedding:
        with connect() as conn:
            conn.execute(
                "INSERT INTO memory_embeddings (memory_id, embedding_model, embedding_json, created_at) VALUES (?, ?, ?, ?)",
                (memory_id, EMBEDDING_MODEL, json.dumps(embedding), now),
            )
    return {"updated": True, "memory_id": memory_id}


def delete_memory(memory_id: int) -> dict[str, Any]:
    initialize_memory_tables()
    with connect() as conn:
        conn.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
        conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
    return {"deleted": True, "memory_id": memory_id}


def get_all_memories() -> list[dict[str, Any]]:
    initialize_memory_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM user_memories ORDER BY pinned DESC, updated_at DESC, id DESC").fetchall()
    return [dict(row) for row in rows]


def infer_memories_from_text(text: str, source: str = "mythos") -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    clean_text = " ".join(text.split())
    patterns = [
        ("goal", r"\b(?:my goal is|goal is|i want to|i need to|i am trying to)\b(.{8,180})"),
        ("preference", r"\b(?:i prefer|i like|i don't like|i hate|i work best)\b(.{8,180})"),
        ("struggle", r"\b(?:i struggle with|struggling with|hard for me|i am stuck on|i get stuck)\b(.{8,180})"),
        ("plan", r"\b(?:my plan is|i plan to|this week i will|next week i will)\b(.{8,180})"),
        ("fact", r"\b(?:remember that|important:|note that)\b(.{8,180})"),
    ]
    for memory_type, pattern in patterns:
        for match in re.finditer(pattern, clean_text, flags=re.IGNORECASE):
            content = match.group(0).strip(" .")
            if len(content) >= 12:
                candidates.append(
                    {
                        "content": content,
                        "memory_type": memory_type,
                        "source": source,
                        "importance": 4 if memory_type in {"goal", "plan"} else 3,
                        "pinned": memory_type in {"goal", "plan"},
                    }
                )
    return candidates[:5]


def autosave_memories(user_text: str, assistant_text: str = "", source: str = "mythos") -> list[dict[str, Any]]:
    saved = []
    for candidate in infer_memories_from_text(user_text, source):
        result = save_memory(**candidate)
        if result.get("saved"):
            saved.append(result)
    return saved
