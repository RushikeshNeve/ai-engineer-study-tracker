from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable


DB_PATH = Path("study_tracker.db")


BUILT_IN_AUTOMATIONS = [
    {
        "name": "Morning Brief",
        "description": "Daily planning brief across study, health, reminders, and priorities.",
        "schedule_type": "daily",
        "run_time": "07:30",
        "day_of_week": "",
        "day_of_month": 1,
        "action_type": "generate_ai_message",
        "prompt": "Generate my morning brief for today: study priorities, health reminders, revision due, and one practical focus.",
    },
    {
        "name": "Evening Health Check",
        "description": "Daily check for gym, diet, protein, calories, steps, and recovery.",
        "schedule_type": "daily",
        "run_time": "21:30",
        "day_of_week": "",
        "day_of_month": 1,
        "action_type": "create_notification",
        "prompt": "Create an evening health check: ask what I ate, whether I trained, steps, protein, and recovery.",
    },
    {
        "name": "Weekly Review",
        "description": "Weekly summary of study, projects, health, wins, misses, and next focus.",
        "schedule_type": "weekly",
        "run_time": "20:00",
        "day_of_week": "Sunday",
        "day_of_month": 1,
        "action_type": "generate_report",
        "prompt": "Generate my full weekly review and next week focus.",
    },
    {
        "name": "DSA Revision Reminder",
        "description": "Daily reminder for due DSA revisions and weak topics.",
        "schedule_type": "daily",
        "run_time": "22:30",
        "day_of_week": "",
        "day_of_month": 1,
        "action_type": "create_notification",
        "prompt": "Check my DSA revision due items and create a short reminder for tonight.",
    },
    {
        "name": "Study Reminder",
        "description": "Daily reminder for Slot 1 and Slot 2 learning priorities.",
        "schedule_type": "daily",
        "run_time": "09:00",
        "day_of_week": "",
        "day_of_month": 1,
        "action_type": "create_notification",
        "prompt": "Remind me what to study today for Slot 1 and Slot 2. Keep it short and actionable.",
    },
    {
        "name": "Monthly Career Report",
        "description": "Monthly report on backend, AI, system design, projects, resume, and interview readiness.",
        "schedule_type": "monthly",
        "run_time": "10:00",
        "day_of_week": "",
        "day_of_month": 1,
        "action_type": "generate_report",
        "prompt": "Generate my monthly career report: backend progress, AI progress, system design, projects, resume gaps, interview readiness, and next month priorities.",
    },
    {
        "name": "Weekly GitHub Activity Summary",
        "description": "Weekly summary of commits, active repos, project progress signals, and portfolio follow-ups.",
        "schedule_type": "weekly",
        "run_time": "19:00",
        "day_of_week": "Sunday",
        "day_of_month": 1,
        "action_type": "generate_report",
        "prompt": "Generate my weekly GitHub activity summary. Include commits, active repos, project momentum, portfolio gaps, and next coding focus.",
    },
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_automation_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS automations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                schedule_type TEXT,
                run_time TEXT,
                day_of_week TEXT,
                day_of_month INTEGER DEFAULT 1,
                action_type TEXT,
                prompt TEXT,
                enabled INTEGER DEFAULT 1,
                last_run_at TEXT,
                next_run_at TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS automation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                automation_id INTEGER,
                automation_name TEXT,
                action_type TEXT,
                status TEXT,
                message TEXT,
                output TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                message TEXT,
                category TEXT,
                priority TEXT,
                source TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_briefings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                briefing_date TEXT UNIQUE,
                morning_brief TEXT,
                evening_brief TEXT,
                study_summary TEXT,
                health_summary TEXT,
                career_summary TEXT,
                created_at TEXT
            );
            """
        )
        seed_builtin_automations(conn)


def parse_run_time(run_time: str) -> time:
    try:
        hour, minute = [int(part) for part in run_time.split(":", 1)]
        return time(hour=hour, minute=minute)
    except Exception:
        return time(hour=9, minute=0)


def calculate_next_run(automation: dict[str, Any], now: datetime | None = None) -> str:
    now = now or datetime.now()
    run_clock = parse_run_time(automation.get("run_time") or "09:00")
    schedule_type = automation.get("schedule_type") or "daily"
    candidate = datetime.combine(now.date(), run_clock)

    if schedule_type == "daily":
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.isoformat()

    if schedule_type == "weekly":
        target_day = automation.get("day_of_week") or "Monday"
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        target_index = weekdays.index(target_day) if target_day in weekdays else 0
        days_ahead = (target_index - now.weekday()) % 7
        candidate = datetime.combine(now.date() + timedelta(days=days_ahead), run_clock)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate.isoformat()

    day_of_month = int(automation.get("day_of_month") or 1)
    year, month = now.year, now.month
    day = min(day_of_month, 28)
    candidate = datetime(year, month, day, run_clock.hour, run_clock.minute)
    if candidate <= now:
        month += 1
        if month > 12:
            month = 1
            year += 1
        candidate = datetime(year, month, day, run_clock.hour, run_clock.minute)
    return candidate.isoformat()


def seed_builtin_automations(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat()
    for automation in BUILT_IN_AUTOMATIONS:
        existing = conn.execute("SELECT id FROM automations WHERE name = ?", (automation["name"],)).fetchone()
        if existing:
            continue
        next_run = calculate_next_run(automation)
        conn.execute(
            """
            INSERT INTO automations (
                name, description, schedule_type, run_time, day_of_week,
                day_of_month, action_type, prompt, enabled, next_run_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                automation["name"],
                automation["description"],
                automation["schedule_type"],
                automation["run_time"],
                automation["day_of_week"],
                automation["day_of_month"],
                automation["action_type"],
                automation["prompt"],
                next_run,
                now,
            ),
        )


def list_automations() -> list[dict[str, Any]]:
    initialize_automation_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM automations ORDER BY enabled DESC, next_run_at, id").fetchall()
    return [dict(row) for row in rows]


def list_automation_logs(limit: int = 50) -> list[dict[str, Any]]:
    initialize_automation_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM automation_logs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def update_automation_enabled(automation_id: int, enabled: bool) -> dict[str, Any]:
    initialize_automation_tables()
    with connect() as conn:
        row = conn.execute("SELECT * FROM automations WHERE id = ?", (automation_id,)).fetchone()
        if not row:
            return {"updated": False, "reason": "not found"}
        automation = dict(row)
        next_run = calculate_next_run(automation) if enabled else automation.get("next_run_at")
        conn.execute(
            "UPDATE automations SET enabled = ?, next_run_at = ? WHERE id = ?",
            (int(enabled), next_run, automation_id),
        )
    return {"updated": True, "automation_id": automation_id, "enabled": enabled}


def log_automation(
    automation: dict[str, Any],
    status: str,
    message: str,
    output: str = "",
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO automation_logs (
                automation_id, automation_name, action_type, status,
                message, output, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                automation.get("id"),
                automation.get("name"),
                automation.get("action_type"),
                status,
                message,
                output,
                datetime.now().isoformat(),
            ),
        )


def automation_category(name: str, action_type: str) -> str:
    lowered = f"{name} {action_type}".lower()
    if "health" in lowered:
        return "health"
    if "career" in lowered or "resume" in lowered or "interview" in lowered:
        return "career"
    if "project" in lowered or "github" in lowered:
        return "project"
    if "study" in lowered or "dsa" in lowered or "brief" in lowered:
        return "study"
    return "system"


def automation_priority(name: str, action_type: str) -> str:
    lowered = f"{name} {action_type}".lower()
    if "dsa" in lowered or "health check" in lowered:
        return "high"
    if "monthly" in lowered or "weekly" in lowered or "brief" in lowered:
        return "medium"
    return "low"


def create_notification(
    title: str,
    message: str,
    category: str = "system",
    priority: str = "medium",
    source: str = "automation",
) -> dict[str, Any]:
    initialize_automation_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (
                title, message, category, priority, source, is_read, created_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (title, message, category, priority, source, datetime.now().isoformat()),
        )
    return {"saved": True, "notification_id": cursor.lastrowid}


def upsert_daily_briefing(
    briefing_date: str,
    morning_brief: str | None = None,
    evening_brief: str | None = None,
    study_summary: str | None = None,
    health_summary: str | None = None,
    career_summary: str | None = None,
) -> dict[str, Any]:
    initialize_automation_tables()
    with connect() as conn:
        existing = conn.execute("SELECT * FROM daily_briefings WHERE briefing_date = ?", (briefing_date,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE daily_briefings
                SET morning_brief = COALESCE(?, morning_brief),
                    evening_brief = COALESCE(?, evening_brief),
                    study_summary = COALESCE(?, study_summary),
                    health_summary = COALESCE(?, health_summary),
                    career_summary = COALESCE(?, career_summary)
                WHERE briefing_date = ?
                """,
                (morning_brief, evening_brief, study_summary, health_summary, career_summary, briefing_date),
            )
            briefing_id = existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO daily_briefings (
                    briefing_date, morning_brief, evening_brief, study_summary,
                    health_summary, career_summary, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    briefing_date,
                    morning_brief or "",
                    evening_brief or "",
                    study_summary or "",
                    health_summary or "",
                    career_summary or "",
                    datetime.now().isoformat(),
                ),
            )
            briefing_id = cursor.lastrowid
    return {"saved": True, "daily_briefing_id": briefing_id}


def persist_automation_output(automation: dict[str, Any], output: str) -> None:
    name = automation.get("name", "")
    action_type = automation.get("action_type", "")
    category = automation_category(name, action_type)
    priority = automation_priority(name, action_type)
    today = date.today().isoformat()

    if name == "Morning Brief":
        upsert_daily_briefing(today, morning_brief=output, study_summary=output)
        create_notification("Morning Brief Ready", output, "study", "medium", name)
    elif name == "Evening Health Check":
        upsert_daily_briefing(today, evening_brief=output, health_summary=output)
        create_notification("Evening Health Check", output, "health", "high", name)
    elif name in {"DSA Revision Reminder", "Study Reminder"}:
        create_notification(name, output, category, priority, name)
    elif name == "Monthly Career Report":
        upsert_daily_briefing(today, career_summary=output)
        create_notification("Monthly Career Report", output, "career", "medium", name)
    elif action_type == "generate_report":
        create_notification(name, output, category, priority, name)
    elif action_type == "create_notification":
        create_notification(name, output, category, priority, name)


def run_automation(automation_id: int, ai_runner: Callable[[str], str]) -> dict[str, Any]:
    initialize_automation_tables()
    with connect() as conn:
        row = conn.execute("SELECT * FROM automations WHERE id = ?", (automation_id,)).fetchone()
    if not row:
        return {"ran": False, "reason": "not found"}

    automation = dict(row)
    try:
        output = ai_runner(automation.get("prompt") or automation.get("name") or "Run automation")
        persist_automation_output(automation, output)
        status = "success"
        message = "Automation completed."
    except Exception as exc:
        output = ""
        status = "failed"
        message = str(exc)

    log_automation(automation, status, message, output)
    next_run = calculate_next_run(automation)
    with connect() as conn:
        conn.execute(
            "UPDATE automations SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (datetime.now().isoformat(), next_run, automation_id),
        )
    return {"ran": status == "success", "status": status, "message": message, "output": output}


def run_due_automations(ai_runner: Callable[[str], str], limit: int = 3) -> list[dict[str, Any]]:
    initialize_automation_tables()
    now = datetime.now().isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM automations
            WHERE enabled = 1
              AND next_run_at IS NOT NULL
              AND next_run_at <= ?
            ORDER BY next_run_at
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()
    results = []
    for row in rows:
        results.append(run_automation(int(row["id"]), ai_runner))
    return results


def latest_notifications(limit: int = 5) -> list[dict[str, Any]]:
    initialize_automation_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM notifications ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def latest_reports(limit: int = 5) -> list[dict[str, Any]]:
    initialize_automation_tables()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM notifications
            WHERE source LIKE '%Report%' OR title LIKE '%Report%'
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_notifications(category: str = "All", priority: str = "All", include_read: bool = True) -> list[dict[str, Any]]:
    initialize_automation_tables()
    clauses = []
    params: list[Any] = []
    if category != "All":
        clauses.append("category = ?")
        params.append(category)
    if priority != "All":
        clauses.append("priority = ?")
        params.append(priority)
    if not include_read:
        clauses.append("is_read = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM notifications {where} ORDER BY is_read ASC, created_at DESC, id DESC",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def mark_notification_read(notification_id: int, is_read: bool = True) -> dict[str, Any]:
    initialize_automation_tables()
    with connect() as conn:
        conn.execute("UPDATE notifications SET is_read = ? WHERE id = ?", (int(is_read), notification_id))
    return {"updated": True, "notification_id": notification_id, "is_read": is_read}


def get_latest_daily_briefing() -> dict[str, Any]:
    initialize_automation_tables()
    with connect() as conn:
        row = conn.execute("SELECT * FROM daily_briefings ORDER BY briefing_date DESC, id DESC LIMIT 1").fetchone()
    return dict(row) if row else {}
