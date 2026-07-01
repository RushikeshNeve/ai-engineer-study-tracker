from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


DB_PATH = Path("study_tracker.db")

MODEL_COST_PER_1M = {
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_observability_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                prompt TEXT,
                response_time_ms INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                error TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tool_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT,
                agent_name TEXT,
                execution_time_ms INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                error TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS router_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT,
                selected_agent TEXT,
                confidence REAL DEFAULT 0,
                execution_time_ms INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS llm_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0,
                response_time_ms INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_retrievals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                memories_found INTEGER DEFAULT 0,
                retrieval_time_ms INTEGER DEFAULT 0,
                created_at TEXT
            );
            """
        )


def estimate_llm_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = MODEL_COST_PER_1M.get(model)
    if not prices:
        for model_prefix, model_prices in MODEL_COST_PER_1M.items():
            if model.startswith(model_prefix):
                prices = model_prices
                break
    prices = prices or MODEL_COST_PER_1M["gpt-4.1-mini"]
    return round((prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000, 6)


def log_agent_execution(agent_name: str, prompt: str, response_time_ms: int, success: bool, error: str = "") -> None:
    initialize_observability_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_executions (agent_name, prompt, response_time_ms, success, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent_name, prompt, int(response_time_ms), int(success), error, datetime.now().isoformat()),
        )


def log_tool_execution(tool_name: str, agent_name: str, execution_time_ms: int, success: bool, error: str = "") -> None:
    initialize_observability_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tool_executions (tool_name, agent_name, execution_time_ms, success, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tool_name, agent_name, int(execution_time_ms), int(success), error, datetime.now().isoformat()),
        )


def log_router_execution(prompt: str, selected_agent: str, confidence: float, execution_time_ms: int) -> None:
    initialize_observability_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO router_executions (prompt, selected_agent, confidence, execution_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (prompt, selected_agent, float(confidence or 0), int(execution_time_ms), datetime.now().isoformat()),
        )


def log_llm_request(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    response_time_ms: int = 0,
) -> None:
    initialize_observability_tables()
    estimated_cost = estimate_llm_cost(model, prompt_tokens, completion_tokens)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_requests (
                model, prompt_tokens, completion_tokens, total_tokens,
                estimated_cost, response_time_ms, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model,
                int(prompt_tokens or 0),
                int(completion_tokens or 0),
                int(total_tokens or prompt_tokens + completion_tokens or 0),
                estimated_cost,
                int(response_time_ms),
                datetime.now().isoformat(),
            ),
        )


def log_memory_retrieval(query: str, memories_found: int, retrieval_time_ms: int) -> None:
    initialize_observability_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_retrievals (query, memories_found, retrieval_time_ms, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (query, int(memories_found), int(retrieval_time_ms), datetime.now().isoformat()),
        )


def read_observability_table(table: str) -> pd.DataFrame:
    initialize_observability_tables()
    allowed = {
        "agent_executions",
        "tool_executions",
        "router_executions",
        "llm_requests",
        "memory_retrievals",
    }
    if table not in allowed:
        return pd.DataFrame()
    with connect() as conn:
        return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC", conn)


def observability_dashboard_summary() -> dict[str, Any]:
    initialize_observability_tables()
    today = date.today().isoformat()
    with connect() as conn:
        llm_today = conn.execute(
            "SELECT COUNT(*) AS requests, COALESCE(SUM(estimated_cost), 0) AS cost, COALESCE(AVG(response_time_ms), 0) AS avg_ms FROM llm_requests WHERE substr(created_at, 1, 10) = ?",
            (today,),
        ).fetchone()
        agent_today = conn.execute(
            "SELECT COALESCE(AVG(response_time_ms), 0) AS avg_ms, COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors FROM agent_executions WHERE substr(created_at, 1, 10) = ?",
            (today,),
        ).fetchone()
        tool_errors = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors FROM tool_executions WHERE substr(created_at, 1, 10) = ?",
            (today,),
        ).fetchone()
        most_agent = conn.execute(
            """
            SELECT agent_name, COUNT(*) AS count
            FROM agent_executions
            GROUP BY agent_name
            ORDER BY count DESC
            LIMIT 1
            """
        ).fetchone()
    avg_response = int(max(float(llm_today["avg_ms"] or 0), float(agent_today["avg_ms"] or 0)))
    return {
        "today_requests": int(llm_today["requests"] or 0),
        "today_cost": round(float(llm_today["cost"] or 0), 4),
        "most_used_agent": most_agent["agent_name"] if most_agent else "None",
        "average_response_time_ms": avg_response,
        "error_count": int(agent_today["errors"] or 0) + int(tool_errors["errors"] or 0),
    }


def daily_metric(table: str, metric: str = "count", days: int = 30) -> pd.DataFrame:
    initialize_observability_tables()
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    if table == "llm_requests" and metric == "tokens":
        select_expr = "COALESCE(SUM(total_tokens), 0)"
    elif table == "llm_requests" and metric == "cost":
        select_expr = "COALESCE(SUM(estimated_cost), 0)"
    elif metric == "errors":
        select_expr = "COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0)"
    elif metric == "latency":
        select_expr = "COALESCE(AVG(response_time_ms), 0)"
    else:
        select_expr = "COUNT(*)"
    with connect() as conn:
        return pd.read_sql_query(
            f"""
            SELECT substr(created_at, 1, 10) AS day, {select_expr} AS value
            FROM {table}
            WHERE substr(created_at, 1, 10) >= ?
            GROUP BY day
            ORDER BY day
            """,
            conn,
            params=(start,),
        )


def top_counts(table: str, column: str, limit: int = 10) -> pd.DataFrame:
    initialize_observability_tables()
    allowed = {
        ("agent_executions", "agent_name"),
        ("tool_executions", "tool_name"),
        ("router_executions", "selected_agent"),
        ("llm_requests", "model"),
    }
    if (table, column) not in allowed:
        return pd.DataFrame()
    with connect() as conn:
        return pd.read_sql_query(
            f"""
            SELECT {column} AS name, COUNT(*) AS count
            FROM {table}
            GROUP BY {column}
            ORDER BY count DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )
