from __future__ import annotations

import io
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from openai_agent import run_health_agent
from tools import (
    WEEKLY_SPLIT,
    calculate_health_score,
    calculate_weekly_avg_protein,
    calculate_weekly_workout_count,
    calculate_weight_trend,
    calculate_burnout_risk,
    calculate_weekly_consistency_score,
    get_backend_course_summary,
    get_dsa_progress_summary,
    get_fitness_profile,
    get_project_progress_summary,
    get_recent_chat_messages,
    get_recent_diet_logs,
    get_recent_gym_sessions,
    get_recent_tool_logs,
    get_revision_due_items,
    get_weight_logs,
    initialize_health_tables,
    save_diet_log,
    save_gym_session,
    save_weight_log,
)


APP_NAME = "AI Engineer Study Tracker"
DB_PATH = Path("study_tracker.db")

SCHEDULE = [
    ("6:00", "Wake up"),
    ("6:30", "Gym travel + pre-workout"),
    ("7:00 - 8:30", "Gym"),
    ("8:30 - 9:00", "Breakfast"),
    ("9:00 - 9:30", "Bath / get ready"),
    ("9:30 - 12:30", "Deep Study Slot 1"),
    ("12:30 - 1:00", "Lunch"),
    ("1:00 - 9:00", "Office"),
    ("9:00 - 10:00", "Dinner"),
    ("10:00 - 11:00", "10k steps"),
    ("11:00 - 12:15", "Light Study Slot 2"),
    ("12:15", "Sleep"),
]

WEEKLY_PLAN = {
    "Monday": ("AI Cohort + Cohort Assignment", "DSA + Revision"),
    "Tuesday": ("System Design + AI Project", "DSA + Project Planning"),
    "Wednesday": ("AI Cohort + AI Project", "DSA + Notes"),
    "Thursday": ("Backend Deep Dive + System Design", "DSA + Backend Revision"),
    "Friday": ("AI Cohort + Project Development", "Weekly Review / Light Reading"),
    "Saturday": ("Project Building", "DSA + Cohort Revision"),
    "Sunday": ("System Design + Backend", "Weekly Planning"),
}

TABLES = [
    "daily_logs",
    "dsa_problems",
    "ai_cohort",
    "system_design",
    "backend_deep_dive",
    "backend_course",
    "system_design_course",
    "fitness_profile",
    "gym_sessions",
    "gym_exercises",
    "diet_logs",
    "weight_logs",
    "health_reports",
    "chatbot_messages",
    "chatbot_tool_logs",
    "projects",
    "notes",
    "weekly_reviews",
    "learning_plans",
    "weekly_ai_reviews",
]

COURSE_LINK = "https://youtu.be/0Rwb4Xmlcwc?si=TDG5hZDWn0HAriFR"

BACKEND_COURSE_TOPICS = {
    "Phase 1 - Backend Fundamentals": [
        "HTTP",
        "HTTPS",
        "DNS",
        "TCP/IP",
        "REST APIs",
        "API Design",
        "JSON",
        "Serialization",
        "Validation",
        "Authentication",
        "Authorization",
        "JWT",
        "Cookies",
        "Sessions",
    ],
    "Phase 2 - Databases": [
        "SQL",
        "NoSQL",
        "PostgreSQL",
        "MongoDB",
        "ACID",
        "Transactions",
        "Indexing",
        "Query Optimization",
        "Database Scaling",
        "Replication",
        "Sharding",
    ],
    "Phase 3 - Caching and Performance": [
        "Caching Fundamentals",
        "Redis",
        "Cache Aside Pattern",
        "TTL",
        "CDN",
        "Reverse Proxy",
        "Load Balancing",
        "Nginx",
        "Rate Limiting",
    ],
    "Phase 4 - Communication and Distributed Systems": [
        "Message Queues",
        "Pub/Sub",
        "RabbitMQ",
        "Kafka",
        "WebSockets",
        "Server-Sent Events",
        "gRPC",
        "Background Jobs",
        "Event-Driven Architecture",
    ],
    "Phase 5 - Security and Reliability": [
        "TLS",
        "Encryption",
        "Hashing",
        "XSS",
        "CSRF",
        "CORS",
        "Logging",
        "Monitoring",
        "Observability",
        "Retries",
        "Idempotency",
        "Circuit Breaker",
    ],
    "Phase 6 - Production and Deployment": [
        "Docker",
        "CI/CD",
        "Environment Variables",
        "Deployment",
        "Horizontal Scaling",
        "Health Checks",
        "API Versioning",
        "Documentation",
        "Testing",
    ],
}

IMPLEMENTATION_IDEAS = {
    "HTTP": "Build a simple HTTP server/client demo.",
    "JWT": "Build an access + refresh token auth demo.",
    "Redis": "Build a cache-aside API demo.",
    "Load Balancing": "Simulate multiple backend servers behind a reverse proxy.",
    "Message Queues": "Build a producer-consumer demo.",
    "WebSockets": "Build a live notification demo.",
    "gRPC": "Build simple service-to-service communication demo.",
    "Rate Limiting": "Build an API rate limiter.",
    "Docker": "Dockerize a small backend service.",
}

SYSTEM_DESIGN_COURSE_SECTIONS = [
    (1, "Introduction", "Fundamentals"),
    (2, "Networking & Communication", "Fundamentals"),
    (3, "Protocols", "Fundamentals"),
    (4, "Architectural Patterns", "Fundamentals"),
    (5, "Web Concepts", "Fundamentals"),
    (6, "Scalability", "Fundamentals"),
    (7, "Storage - Database and Storage", "Fundamentals"),
    (8, "Performance - Concepts, Tools & Techniques", "Fundamentals"),
    (9, "Reliability, Availability & Disaster Recovery", "Fundamentals"),
    (10, "Security in System Design", "Fundamentals"),
    (11, "The System Design Blueprint", "Blueprint"),
    (12, "Design a URL Shortener", "Case Studies"),
    (13, "Design a Ticketing System (BookMyShow)", "Case Studies"),
    (14, "Design a News Feed (Twitter/Instagram)", "Case Studies"),
    (15, "Design a Notification System", "Case Studies"),
    (16, "Design a Chat Application (WhatsApp)", "Case Studies"),
    (17, "Design an Auction Platform (eBay)", "Case Studies"),
    (18, "Design an Online Rental Platform (Airbnb)", "Case Studies"),
    (19, "Design a Cloud Storage Solution (Google Drive)", "Case Studies"),
    (20, "Design a Video Sharing Platform (YouTube)", "Case Studies"),
    (21, "Design a Search Engine (Google)", "Case Studies"),
    (22, "Design an E-Commerce Platform (Amazon)", "Case Studies"),
    (23, "Design a Taxi Hailing App (Uber)", "Case Studies"),
    (24, "Design a Collaborative Document Editor (Google Docs)", "Case Studies"),
    (25, "Final Prep, Mindset & Moving Forward", "Revision"),
]

SYSTEM_DESIGN_PHASES = ["Fundamentals", "Blueprint", "Case Studies", "Revision"]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                day TEXT NOT NULL,
                slot1_plan TEXT,
                slot1_done INTEGER DEFAULT 0,
                slot2_plan TEXT,
                slot2_done INTEGER DEFAULT 0,
                study_minutes INTEGER DEFAULT 0,
                dsa_done_count INTEGER DEFAULT 0,
                gym_done INTEGER DEFAULT 0,
                steps_done INTEGER DEFAULT 0,
                mood TEXT,
                blockers TEXT,
                reflection TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dsa_problems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                problem_name TEXT NOT NULL,
                topic TEXT,
                pattern TEXT,
                difficulty TEXT,
                platform TEXT,
                link TEXT,
                time_taken_minutes INTEGER DEFAULT 0,
                status TEXT,
                solved_without_help INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                mistakes TEXT,
                revision_due_date TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS ai_cohort (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER,
                module_name TEXT NOT NULL,
                status TEXT,
                lecture_done INTEGER DEFAULT 0,
                assignment_done INTEGER DEFAULT 0,
                implementation_done INTEGER DEFAULT 0,
                notes_done INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                key_learning TEXT,
                blockers TEXT,
                completion_percentage INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS system_design (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                system_name TEXT NOT NULL,
                topic TEXT,
                status TEXT,
                requirements_done INTEGER DEFAULT 0,
                hld_done INTEGER DEFAULT 0,
                database_design_done INTEGER DEFAULT 0,
                scaling_done INTEGER DEFAULT 0,
                tradeoffs_done INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS backend_deep_dive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                topic TEXT NOT NULL,
                subtopic TEXT,
                status TEXT,
                resource TEXT,
                implementation_done INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS backend_course (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_started TEXT,
                topic TEXT NOT NULL,
                subtopic TEXT,
                phase TEXT,
                source_link TEXT,
                status TEXT,
                video_done INTEGER DEFAULT 0,
                notes_done INTEGER DEFAULT 0,
                mini_implementation_done INTEGER DEFAULT 0,
                interview_ready INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 1,
                key_learning TEXT,
                implementation_idea TEXT,
                revision_due_date TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_design_course (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_number INTEGER NOT NULL,
                section_name TEXT NOT NULL,
                phase TEXT,
                status TEXT,
                notes_done INTEGER DEFAULT 0,
                diagrams_done INTEGER DEFAULT 0,
                implementation_done INTEGER DEFAULT 0,
                interview_ready INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 1,
                study_hours REAL DEFAULT 0,
                key_learning TEXT,
                revision_due_date TEXT,
                notes TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                category TEXT,
                status TEXT,
                progress_percentage INTEGER DEFAULT 0,
                github_link TEXT,
                demo_link TEXT,
                current_task TEXT,
                next_task TEXT,
                blockers TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                linked_track TEXT
            );

            CREATE TABLE IF NOT EXISTS weekly_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                week_end TEXT NOT NULL,
                wins TEXT,
                misses TEXT,
                total_study_hours REAL DEFAULT 0,
                dsa_count INTEGER DEFAULT 0,
                project_progress TEXT,
                backend_topics_completed INTEGER DEFAULT 0,
                backend_implementation_count INTEGER DEFAULT 0,
                backend_weak_topics TEXT,
                backend_next_week_focus TEXT,
                system_design_sections_completed INTEGER DEFAULT 0,
                system_design_study_hours REAL DEFAULT 0,
                system_design_weak_areas TEXT,
                system_design_next_focus TEXT,
                biggest_learning TEXT,
                next_week_focus TEXT,
                burnout_level INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learning_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                plan_type TEXT,
                focus_area TEXT,
                recommended_tasks TEXT,
                reasoning TEXT,
                estimated_minutes INTEGER DEFAULT 0,
                priority TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS weekly_ai_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT,
                week_end TEXT,
                study_score REAL DEFAULT 0,
                health_score REAL DEFAULT 0,
                consistency_score REAL DEFAULT 0,
                burnout_risk TEXT,
                wins TEXT,
                misses TEXT,
                weak_areas TEXT,
                next_week_focus TEXT,
                recommendations TEXT,
                created_at TEXT
            );
            """
        )
        ensure_weekly_backend_columns(conn)
        ensure_weekly_system_design_columns(conn)
        preload_backend_course(conn)
        preload_system_design_course(conn)


def ensure_weekly_backend_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(weekly_reviews)").fetchall()}
    migrations = {
        "backend_topics_completed": "ALTER TABLE weekly_reviews ADD COLUMN backend_topics_completed INTEGER DEFAULT 0",
        "backend_implementation_count": "ALTER TABLE weekly_reviews ADD COLUMN backend_implementation_count INTEGER DEFAULT 0",
        "backend_weak_topics": "ALTER TABLE weekly_reviews ADD COLUMN backend_weak_topics TEXT",
        "backend_next_week_focus": "ALTER TABLE weekly_reviews ADD COLUMN backend_next_week_focus TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            conn.execute(sql)


def ensure_weekly_system_design_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(weekly_reviews)").fetchall()}
    migrations = {
        "system_design_sections_completed": "ALTER TABLE weekly_reviews ADD COLUMN system_design_sections_completed INTEGER DEFAULT 0",
        "system_design_study_hours": "ALTER TABLE weekly_reviews ADD COLUMN system_design_study_hours REAL DEFAULT 0",
        "system_design_weak_areas": "ALTER TABLE weekly_reviews ADD COLUMN system_design_weak_areas TEXT",
        "system_design_next_focus": "ALTER TABLE weekly_reviews ADD COLUMN system_design_next_focus TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            conn.execute(sql)


def preload_backend_course(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM backend_course").fetchone()[0]
    if existing:
        return

    now = datetime.now().isoformat()
    for phase, topics in BACKEND_COURSE_TOPICS.items():
        for topic in topics:
            conn.execute(
                """
                INSERT INTO backend_course (
                    date_started, topic, subtopic, phase, source_link, status,
                    video_done, notes_done, mini_implementation_done, interview_ready,
                    confidence, key_learning, implementation_idea, revision_due_date,
                    notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    topic,
                    "",
                    phase,
                    COURSE_LINK,
                    "Not Started",
                    1,
                    "",
                    IMPLEMENTATION_IDEAS.get(topic, ""),
                    "",
                    "",
                    now,
                ),
            )


def preload_system_design_course(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM system_design_course").fetchone()[0]
    if existing:
        return

    completed_at = datetime.now().isoformat()
    for section_number, section_name, phase in SYSTEM_DESIGN_COURSE_SECTIONS:
        completed = section_number <= 4
        conn.execute(
            """
            INSERT INTO system_design_course (
                section_number, section_name, phase, status, notes_done,
                diagrams_done, implementation_done, interview_ready, confidence,
                study_hours, key_learning, revision_due_date, notes, completed_at
            )
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, 0, ?, ?, ?, ?)
            """,
            (
                section_number,
                section_name,
                phase,
                "Completed" if completed else "Not Started",
                int(completed),
                3 if completed else 1,
                "",
                "",
                "",
                completed_at if completed else "",
            ),
        )


def read_table(table: str) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC", conn)


def insert_row(table: str, data: dict) -> None:
    keys = list(data.keys())
    placeholders = ", ".join(["?"] * len(keys))
    columns = ", ".join(keys)
    values = [serialize_value(data[key]) for key in keys]
    with connect() as conn:
        conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)


def update_row(table: str, row_id: int, data: dict) -> None:
    assignments = ", ".join([f"{key} = ?" for key in data])
    values = [serialize_value(value) for value in data.values()]
    values.append(row_id)
    with connect() as conn:
        conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", values)


def serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def current_week_range(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def planned_slots(day_name: str) -> tuple[str, str]:
    return WEEKLY_PLAN.get(day_name, ("", ""))


def metric_card(label: str, value, help_text: str | None = None) -> None:
    st.metric(label, value, help=help_text)


def show_dataframe(df: pd.DataFrame, empty_message: str = "No records yet.") -> None:
    if df.empty:
        st.info(empty_message)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def parse_date(value, fallback: date | None = None) -> date:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback or date.today()
    return parsed.date()


def backend_course_metrics(df: pd.DataFrame, today: date) -> dict:
    if df.empty:
        return {
            "total": 0,
            "completed": 0,
            "interview_ready": 0,
            "avg_confidence": 0,
            "progress": 0,
            "revision_due": pd.DataFrame(),
        }

    completed = int((df["status"] == "Completed").sum())
    total = len(df)
    revision_dates = pd.to_datetime(df["revision_due_date"], errors="coerce")
    due = df[revision_dates <= pd.Timestamp(today)]
    return {
        "total": total,
        "completed": completed,
        "interview_ready": int(df["interview_ready"].fillna(0).astype(int).sum()),
        "avg_confidence": round(float(df["confidence"].mean()), 1),
        "progress": int(completed / total * 100) if total else 0,
        "revision_due": due,
    }


def backend_week_stats(df: pd.DataFrame, week_start: date, week_end: date) -> dict:
    if df.empty:
        return {
            "completed_this_week": 0,
            "implementation_count": 0,
            "weak_topics": "",
            "next_focus": "",
        }

    started_dates = pd.to_datetime(df["date_started"], errors="coerce")
    week_df = df[(started_dates >= pd.Timestamp(week_start)) & (started_dates <= pd.Timestamp(week_end))]
    completed_week = int((week_df["status"] == "Completed").sum())
    implementation_count = int(week_df["mini_implementation_done"].fillna(0).astype(int).sum())
    weak = df[(df["confidence"] <= 2) | ((df["video_done"] == 1) & (df["mini_implementation_done"] == 0))]
    weak_topics = ", ".join(weak["topic"].head(5).tolist())
    next_focus_df = df[df["status"].isin(["Not Started", "In Progress", "Revising"])].head(3)
    next_focus = ", ".join(next_focus_df["topic"].tolist())
    return {
        "completed_this_week": completed_week,
        "implementation_count": implementation_count,
        "weak_topics": weak_topics,
        "next_focus": next_focus,
    }


def system_design_course_metrics(df: pd.DataFrame, today: date) -> dict:
    if df.empty:
        return {
            "total": 0,
            "completed": 0,
            "interview_ready": 0,
            "avg_confidence": 0,
            "progress": 0,
            "revision_due": pd.DataFrame(),
        }

    completed = int((df["status"] == "Completed").sum())
    total = len(df)
    revision_dates = pd.to_datetime(df["revision_due_date"], errors="coerce")
    due = df[revision_dates <= pd.Timestamp(today)]
    return {
        "total": total,
        "completed": completed,
        "interview_ready": int(df["interview_ready"].fillna(0).astype(int).sum()),
        "avg_confidence": round(float(df["confidence"].mean()), 1),
        "progress": int(completed / total * 100) if total else 0,
        "revision_due": due,
    }


def system_design_week_stats(df: pd.DataFrame, week_start: date, week_end: date) -> dict:
    if df.empty:
        return {
            "completed_this_week": 0,
            "study_hours": 0.0,
            "weak_areas": "",
            "next_focus": "",
        }

    completed_dates = pd.to_datetime(df["completed_at"], errors="coerce")
    week_df = df[(completed_dates >= pd.Timestamp(week_start)) & (completed_dates <= pd.Timestamp(week_end))]
    weak = df[(df["confidence"] <= 2) & (df["status"] != "Completed")]
    weak_areas = ", ".join(weak.sort_values("section_number")["section_name"].head(5).tolist())
    next_focus_df = df[df["status"].isin(["Not Started", "In Progress"])].sort_values("section_number").head(3)
    next_focus = ", ".join(next_focus_df["section_name"].tolist())
    return {
        "completed_this_week": int((week_df["status"] == "Completed").sum()),
        "study_hours": round(float(week_df["study_hours"].fillna(0).sum()), 1),
        "weak_areas": weak_areas,
        "next_focus": next_focus,
    }


def dashboard() -> None:
    today = date.today()
    day_name = today.strftime("%A")
    week_start, week_end = current_week_range(today)
    slot1, slot2 = planned_slots(day_name)

    st.title(APP_NAME)
    st.caption("A simple local tracker for the next 6 months of Backend + AI Engineer transition work.")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader(f"Today: {day_name}")
        st.write(f"**Slot 1:** {slot1}")
        st.write(f"**Slot 2:** {slot2}")
    with c2:
        st.subheader("Daily Schedule")
        st.dataframe(pd.DataFrame(SCHEDULE, columns=["Time", "Plan"]), hide_index=True, use_container_width=True)

    daily = read_table("daily_logs")
    dsa = read_table("dsa_problems")
    cohort = read_table("ai_cohort")
    projects = read_table("projects")
    backend_course = read_table("backend_course")
    system_design_course = read_table("system_design_course")
    learning_plans = read_table("learning_plans")
    weekly_ai_reviews = read_table("weekly_ai_reviews")

    if not daily.empty:
        daily["date_dt"] = pd.to_datetime(daily["date"], errors="coerce")
        week_daily = daily[(daily["date_dt"].dt.date >= week_start) & (daily["date_dt"].dt.date <= week_end)]
    else:
        week_daily = pd.DataFrame()

    if not dsa.empty:
        dsa["date_dt"] = pd.to_datetime(dsa["date"], errors="coerce")
        week_dsa = dsa[(dsa["date_dt"].dt.date >= week_start) & (dsa["date_dt"].dt.date <= week_end)]
        due_today = dsa[pd.to_datetime(dsa["revision_due_date"], errors="coerce").dt.date == today]
    else:
        week_dsa = pd.DataFrame()
        due_today = pd.DataFrame()

    total_minutes = int(week_daily["study_minutes"].sum()) if not week_daily.empty else 0
    dsa_count = int(week_daily["dsa_done_count"].sum()) if not week_daily.empty else len(week_dsa)
    cohort_progress = int(cohort["completion_percentage"].mean()) if not cohort.empty else 0
    project_progress = int(projects["progress_percentage"].mean()) if not projects.empty else 0
    consistency = int(week_daily["date"].nunique()) if not week_daily.empty else 0
    backend_metrics = backend_course_metrics(backend_course, today)
    backend_week = backend_week_stats(backend_course, week_start, week_end)
    system_design_metrics = system_design_course_metrics(system_design_course, today)
    latest_learning_plan = pd.Series(dtype=object)
    if not learning_plans.empty:
        today_plans = learning_plans[learning_plans["date"] == today.isoformat()]
        source_plans = today_plans if not today_plans.empty else learning_plans
        latest_learning_plan = source_plans.sort_values(["date", "id"]).iloc[-1]
    dsa_summary = get_dsa_progress_summary()
    backend_summary = get_backend_course_summary()
    revision_due_items = get_revision_due_items()
    project_summary = get_project_progress_summary()
    consistency_summary = calculate_weekly_consistency_score()
    burnout_summary = calculate_burnout_risk()
    latest_weekly_review = pd.Series(dtype=object)
    if not weekly_ai_reviews.empty:
        latest_weekly_review = weekly_ai_reviews.sort_values(["week_start", "id"]).iloc[-1]

    st.subheader("This Week")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        metric_card("Study Hours", round(total_minutes / 60, 1))
    with m2:
        metric_card("DSA Solved", dsa_count)
    with m3:
        metric_card("AI Progress", f"{cohort_progress}%")
    with m4:
        metric_card("Project Progress", f"{project_progress}%")
    with m5:
        metric_card("Consistency", f"{consistency}/7")

    st.subheader("Learning Coach")
    l1, l2, l3, l4 = st.columns(4)
    weak_topics = ", ".join((dsa_summary.get("weak_topics") or [])[:3] + (backend_summary.get("weak_topics") or [])[:3])
    with l1:
        metric_card("Weekly Study Consistency", f"{consistency}/7")
    with l2:
        metric_card("Revision Due", revision_due_items.get("total_due", 0))
    with l3:
        metric_card("Weak Topics", weak_topics or "None logged")
    with l4:
        metric_card("Project Focus", project_summary.get("project_focus") or "No active project")
    if latest_learning_plan.empty:
        st.caption("Generate a Learning Coach Agent plan to show today's AI-generated plan here.")
    else:
        st.write(f"**Today's AI Plan:** {latest_learning_plan.get('focus_area', '')}")
        st.caption(str(latest_learning_plan.get("recommended_tasks", "")))

    st.subheader("Weekly Review Agent")
    w1, w2, w3, w4, w5 = st.columns(5)
    with w1:
        metric_card("Latest Weekly Score", latest_weekly_review.get("study_score", 0) if not latest_weekly_review.empty else 0)
    with w2:
        metric_card("Consistency Score", latest_weekly_review.get("consistency_score", consistency_summary.get("consistency_score", 0)) if not latest_weekly_review.empty else consistency_summary.get("consistency_score", 0))
    with w3:
        metric_card("Burnout Risk", latest_weekly_review.get("burnout_risk", burnout_summary.get("burnout_risk", "Low")) if not latest_weekly_review.empty else burnout_summary.get("burnout_risk", "Low"))
    with w4:
        metric_card("Biggest Win", latest_weekly_review.get("wins", "No AI review yet") if not latest_weekly_review.empty else "No AI review yet")
    with w5:
        metric_card("Biggest Miss", latest_weekly_review.get("misses", "No AI review yet") if not latest_weekly_review.empty else "No AI review yet")
    if not latest_weekly_review.empty:
        st.caption(f"Next week focus: {latest_weekly_review.get('next_week_focus', '')}")

    st.subheader("Backend Course")
    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        metric_card("Course Progress", f"{backend_metrics['progress']}%")
    with b2:
        metric_card("Completed This Week", backend_week["completed_this_week"])
    with b3:
        metric_card("Revisions Due", len(backend_metrics["revision_due"]))
    with b4:
        metric_card("Avg Confidence", backend_metrics["avg_confidence"])
    with b5:
        metric_card("Interview Ready", backend_metrics["interview_ready"])

    st.subheader("System Design Course")
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    with s1:
        metric_card("Total Sections", system_design_metrics["total"])
    with s2:
        metric_card("Completed", system_design_metrics["completed"])
    with s3:
        metric_card("Progress", f"{system_design_metrics['progress']}%")
    with s4:
        metric_card("Avg Confidence", system_design_metrics["avg_confidence"])
    with s5:
        metric_card("Interview Ready", system_design_metrics["interview_ready"])
    with s6:
        metric_card("Revision Due", len(system_design_metrics["revision_due"]))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Study Minutes by Day")
        if week_daily.empty:
            st.info("Add daily logs to see this chart.")
        else:
            chart_df = week_daily.groupby("day", as_index=False)["study_minutes"].sum()
            st.plotly_chart(px.bar(chart_df, x="day", y="study_minutes"), use_container_width=True)

    with c2:
        st.subheader("DSA Problems by Topic")
        if dsa.empty:
            st.info("Add DSA problems to see topic distribution.")
        else:
            topic_df = dsa.groupby("topic", dropna=False, as_index=False)["id"].count()
            topic_df.columns = ["topic", "count"]
            st.plotly_chart(px.bar(topic_df, x="topic", y="count"), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Track Progress")
        st.write("AI Cohort")
        st.progress(cohort_progress / 100)
        st.write("Projects")
        st.progress(project_progress / 100)
        st.write("Backend Course")
        st.progress(backend_metrics["progress"] / 100)
        st.write("System Design Course")
        st.progress(system_design_metrics["progress"] / 100)
    with c2:
        st.subheader("Upcoming DSA Revisions")
        if due_today.empty:
            st.success("No DSA revisions due today.")
        else:
            show_dataframe(due_today[["problem_name", "topic", "difficulty", "revision_due_date"]])

    st.subheader("Project Progress")
    if projects.empty:
        st.info("Add projects to see progress.")
    else:
        for _, row in projects.sort_values("progress_percentage", ascending=False).iterrows():
            st.write(f"**{row['project_name']}** - {row.get('status', '')}")
            st.progress(int(row["progress_percentage"] or 0) / 100)


def daily_log_page() -> None:
    st.title("Daily Log")
    selected_date = st.date_input("Date", value=date.today())
    day_name = selected_date.strftime("%A")
    slot1, slot2 = planned_slots(day_name)

    st.info(f"{day_name} plan: Slot 1 - {slot1} | Slot 2 - {slot2}")

    with st.form("daily_log_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            slot1_done = st.checkbox("Slot 1 done")
            study_minutes = st.number_input("Study minutes", min_value=0, max_value=1000, value=0, step=15)
            gym_done = st.checkbox("Gym done")
            mood = st.selectbox("Mood", ["Focused", "Good", "Okay", "Tired", "Stressed"])
        with c2:
            slot2_done = st.checkbox("Slot 2 done")
            dsa_done_count = st.number_input("DSA count", min_value=0, max_value=50, value=0)
            steps_done = st.checkbox("10k steps done")
        blockers = st.text_area("Blockers")
        reflection = st.text_area("Reflection")
        submitted = st.form_submit_button("Save Daily Log")

    if submitted:
        insert_row(
            "daily_logs",
            {
                "date": selected_date,
                "day": day_name,
                "slot1_plan": slot1,
                "slot1_done": slot1_done,
                "slot2_plan": slot2,
                "slot2_done": slot2_done,
                "study_minutes": study_minutes,
                "dsa_done_count": dsa_done_count,
                "gym_done": gym_done,
                "steps_done": steps_done,
                "mood": mood,
                "blockers": blockers,
                "reflection": reflection,
                "created_at": datetime.now(),
            },
        )
        st.success("Daily log saved.")

    show_dataframe(read_table("daily_logs"))


def dsa_tracker_page() -> None:
    st.title("DSA Tracker")
    solved_date = st.date_input("Solved date", value=date.today())
    suggested_revision = solved_date + timedelta(days=3)

    with st.form("dsa_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            problem_name = st.text_input("Problem name")
            topic = st.text_input("Topic", placeholder="Arrays, DP, Graphs")
            difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        with c2:
            pattern = st.text_input("Pattern")
            platform = st.selectbox("Platform", ["LeetCode", "CodeStudio", "GeeksForGeeks", "Other"])
            status = st.selectbox("Status", ["Solved", "Need Revision", "Attempted", "Skipped"])
        with c3:
            time_taken = st.number_input("Time taken minutes", min_value=0, max_value=500, value=0)
            confidence = st.slider("Confidence", 0, 10, 5)
            solved_without_help = st.checkbox("Solved without help")
        link = st.text_input("Link")
        revision_due_date = st.date_input("Revision due date", value=suggested_revision)
        mistakes = st.text_area("Mistakes")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add DSA Problem")

    if submitted:
        if not problem_name.strip():
            st.error("Problem name is required.")
        else:
            insert_row(
                "dsa_problems",
                {
                    "date": solved_date,
                    "problem_name": problem_name,
                    "topic": topic,
                    "pattern": pattern,
                    "difficulty": difficulty,
                    "platform": platform,
                    "link": link,
                    "time_taken_minutes": time_taken,
                    "status": status,
                    "solved_without_help": solved_without_help,
                    "confidence": confidence,
                    "mistakes": mistakes,
                    "revision_due_date": revision_due_date,
                    "notes": notes,
                },
            )
            st.success("DSA problem saved.")

    df = read_table("dsa_problems")
    st.subheader("Metrics")
    c1, c2, c3, c4, c5 = st.columns(5)
    solved = df[df["status"] == "Solved"] if not df.empty else pd.DataFrame()
    with c1:
        metric_card("Total Solved", len(solved))
    with c2:
        metric_card("Easy", int((df["difficulty"] == "Easy").sum()) if not df.empty else 0)
    with c3:
        metric_card("Medium", int((df["difficulty"] == "Medium").sum()) if not df.empty else 0)
    with c4:
        metric_card("Hard", int((df["difficulty"] == "Hard").sum()) if not df.empty else 0)
    with c5:
        avg_conf = round(float(df["confidence"].mean()), 1) if not df.empty else 0
        metric_card("Avg Confidence", avg_conf)

    if not df.empty:
        due_today = df[pd.to_datetime(df["revision_due_date"], errors="coerce").dt.date == date.today()]
        st.metric("Revision due today", len(due_today))

        st.subheader("Filters")
        fc1, fc2, fc3 = st.columns(3)
        topic_filter = fc1.selectbox("Topic filter", ["All"] + sorted([x for x in df["topic"].dropna().unique() if x]))
        difficulty_filter = fc2.selectbox("Difficulty filter", ["All", "Easy", "Medium", "Hard"])
        status_filter = fc3.selectbox("Status filter", ["All"] + sorted([x for x in df["status"].dropna().unique() if x]))
        filtered = df.copy()
        if topic_filter != "All":
            filtered = filtered[filtered["topic"] == topic_filter]
        if difficulty_filter != "All":
            filtered = filtered[filtered["difficulty"] == difficulty_filter]
        if status_filter != "All":
            filtered = filtered[filtered["status"] == status_filter]
        show_dataframe(filtered)
    else:
        show_dataframe(df)


def ai_cohort_page() -> None:
    st.title("AI Cohort Tracker")
    with st.form("ai_cohort_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            week = st.number_input("Week", min_value=1, max_value=30, value=1)
            module_name = st.text_input("Module name")
            status = st.selectbox("Status", ["Not Started", "In Progress", "Done", "Blocked"])
            confidence = st.slider("Confidence", 0, 10, 5)
        with c2:
            lecture_done = st.checkbox("Lecture done")
            assignment_done = st.checkbox("Assignment done")
            implementation_done = st.checkbox("Implementation done")
            notes_done = st.checkbox("Notes done")
        key_learning = st.text_area("Key learning")
        blockers = st.text_area("Blockers")
        submitted = st.form_submit_button("Save Module")

    if submitted:
        completion = int(sum([lecture_done, assignment_done, implementation_done, notes_done]) / 4 * 100)
        insert_row(
            "ai_cohort",
            {
                "week": week,
                "module_name": module_name,
                "status": status,
                "lecture_done": lecture_done,
                "assignment_done": assignment_done,
                "implementation_done": implementation_done,
                "notes_done": notes_done,
                "confidence": confidence,
                "key_learning": key_learning,
                "blockers": blockers,
                "completion_percentage": completion,
            },
        )
        st.success("AI cohort module saved.")

    df = read_table("ai_cohort")
    if not df.empty:
        st.metric("Average completion", f"{int(df['completion_percentage'].mean())}%")
        st.progress(int(df["completion_percentage"].mean()) / 100)
    show_dataframe(df)


def system_design_page() -> None:
    st.title("System Design Tracker")
    with st.form("system_design_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            practice_date = st.date_input("Date", value=date.today())
            system_name = st.text_input("System name")
            topic = st.text_input("Topic")
            status = st.selectbox("Status", ["Not Started", "In Progress", "Done", "Blocked"])
        with c2:
            requirements_done = st.checkbox("Requirements done")
            hld_done = st.checkbox("HLD done")
            database_design_done = st.checkbox("Database design done")
            scaling_done = st.checkbox("Scaling done")
            tradeoffs_done = st.checkbox("Tradeoffs done")
            confidence = st.slider("Confidence", 0, 10, 5)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save System Design Practice")

    if submitted:
        insert_row(
            "system_design",
            {
                "date": practice_date,
                "system_name": system_name,
                "topic": topic,
                "status": status,
                "requirements_done": requirements_done,
                "hld_done": hld_done,
                "database_design_done": database_design_done,
                "scaling_done": scaling_done,
                "tradeoffs_done": tradeoffs_done,
                "confidence": confidence,
                "notes": notes,
            },
        )
        st.success("System design entry saved.")

    show_dataframe(read_table("system_design"))


def system_design_course_page() -> None:
    st.title("System Design Course Tracker")

    df = read_table("system_design_course")
    today = date.today()
    metrics = system_design_course_metrics(df, today)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        metric_card("Total Sections", metrics["total"])
    with c2:
        metric_card("Completed", metrics["completed"])
    with c3:
        metric_card("Progress", f"{metrics['progress']}%")
    with c4:
        metric_card("Avg Confidence", metrics["avg_confidence"])
    with c5:
        metric_card("Interview Ready", metrics["interview_ready"])
    with c6:
        metric_card("Revision Due", len(metrics["revision_due"]))
    st.progress(metrics["progress"] / 100 if metrics["total"] else 0)

    st.subheader("Progress by Phase")
    if df.empty:
        st.info("No system design course sections yet.")
    else:
        for phase in SYSTEM_DESIGN_PHASES:
            phase_df = df[df["phase"] == phase]
            completed = int((phase_df["status"] == "Completed").sum())
            total = len(phase_df)
            progress = int(completed / total * 100) if total else 0
            st.write(f"**{phase}** - {completed}/{total} sections")
            st.progress(progress / 100)

    st.subheader("Edit Section")
    if df.empty:
        st.info("No sections available.")
        return

    section_options = {
        f"{int(row['section_number'])}. {row['section_name']}": row["id"]
        for _, row in df.sort_values("section_number").iterrows()
    }
    selected_label = st.selectbox("Select section", list(section_options.keys()))
    selected_id = section_options[selected_label]
    selected_row = df[df["id"] == selected_id].iloc[0]
    status_values = ["Not Started", "In Progress", "Completed", "Revising"]
    current_status = selected_row["status"] if selected_row["status"] in status_values else "Not Started"

    with st.form("system_design_course_form"):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Section", value=f"{int(selected_row['section_number'])}. {selected_row['section_name']}", disabled=True)
            st.text_input("Phase", value=selected_row["phase"], disabled=True)
            status = st.selectbox("Status", status_values, index=status_values.index(current_status))
            confidence = st.slider("Confidence", 1, 5, int(selected_row["confidence"]) if selected_row["confidence"] else 1)
            study_hours = st.number_input(
                "Study hours",
                min_value=0.0,
                max_value=200.0,
                value=float(selected_row["study_hours"] or 0),
                step=0.5,
            )
            revision_due_date = st.date_input(
                "Revision due date",
                value=parse_date(selected_row["revision_due_date"], date.today() + timedelta(days=7)),
            )
        with c2:
            notes_done = st.checkbox("Notes done", value=bool(selected_row["notes_done"]))
            diagrams_done = st.checkbox("Diagrams done", value=bool(selected_row["diagrams_done"]))
            implementation_done = st.checkbox("Implementation done", value=bool(selected_row["implementation_done"]))
            interview_ready = st.checkbox("Interview ready", value=bool(selected_row["interview_ready"]))
        key_learning = st.text_area("Key learning", value=selected_row["key_learning"] if selected_row["key_learning"] else "")
        notes = st.text_area("Notes", value=selected_row["notes"] if selected_row["notes"] else "")
        submitted = st.form_submit_button("Save Section")

    if submitted:
        completed_at = selected_row["completed_at"]
        if status == "Completed" and not completed_at:
            completed_at = datetime.now()
        elif status != "Completed":
            completed_at = ""

        update_row(
            "system_design_course",
            int(selected_row["id"]),
            {
                "status": status,
                "notes_done": notes_done,
                "diagrams_done": diagrams_done,
                "implementation_done": implementation_done,
                "interview_ready": interview_ready,
                "confidence": confidence,
                "study_hours": study_hours,
                "key_learning": key_learning,
                "revision_due_date": revision_due_date,
                "notes": notes,
                "completed_at": completed_at,
            },
        )
        st.success("System design course section updated.")
        st.rerun()

    df = read_table("system_design_course")

    st.subheader("Visualizations")
    v1, v2 = st.columns(2)
    with v1:
        chart_df = df.sort_values("section_number")
        st.plotly_chart(
            px.bar(chart_df, x="section_number", y="confidence", color="phase", title="Confidence by Section"),
            use_container_width=True,
        )
    with v2:
        hours_df = df.groupby("phase", as_index=False)["study_hours"].sum()
        st.plotly_chart(px.bar(hours_df, x="phase", y="study_hours", title="Study Hours by Phase"), use_container_width=True)

    st.subheader("Sections")
    f1, f2 = st.columns(2)
    status_filter = f1.selectbox("Status filter", ["All", "Completed", "In Progress", "Not Started"])
    ready_filter = f2.selectbox("Interview readiness filter", ["All", "Interview Ready", "Not Interview Ready"])

    filtered = df.copy()
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if ready_filter == "Interview Ready":
        filtered = filtered[filtered["interview_ready"] == 1]
    elif ready_filter == "Not Interview Ready":
        filtered = filtered[filtered["interview_ready"] == 0]

    display_columns = [
        "section_number",
        "section_name",
        "phase",
        "status",
        "notes_done",
        "diagrams_done",
        "implementation_done",
        "interview_ready",
        "confidence",
        "study_hours",
        "revision_due_date",
        "completed_at",
    ]
    show_dataframe(filtered.sort_values("section_number")[display_columns])


def backend_page() -> None:
    st.title("Backend Deep Dive")
    with st.form("backend_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            entry_date = st.date_input("Date", value=date.today())
            topic = st.text_input("Topic")
            subtopic = st.text_input("Subtopic")
            status = st.selectbox("Status", ["Not Started", "In Progress", "Done", "Blocked"])
        with c2:
            resource = st.text_input("Resource")
            implementation_done = st.checkbox("Implementation done")
            confidence = st.slider("Confidence", 0, 10, 5)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Backend Topic")

    if submitted:
        insert_row(
            "backend_deep_dive",
            {
                "date": entry_date,
                "topic": topic,
                "subtopic": subtopic,
                "status": status,
                "resource": resource,
                "implementation_done": implementation_done,
                "confidence": confidence,
                "notes": notes,
            },
        )
        st.success("Backend topic saved.")

    show_dataframe(read_table("backend_deep_dive"))


def backend_course_page() -> None:
    st.title("Backend Course Tracker")
    st.markdown(f"Course link: [{COURSE_LINK}]({COURSE_LINK})")

    df = read_table("backend_course")
    today = date.today()
    metrics = backend_course_metrics(df, today)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Total Topics", metrics["total"])
    with c2:
        metric_card("Completed", metrics["completed"])
    with c3:
        metric_card("Interview Ready", metrics["interview_ready"])
    with c4:
        metric_card("Avg Confidence", metrics["avg_confidence"])
    with c5:
        metric_card("Overall Progress", f"{metrics['progress']}%")
    st.progress(metrics["progress"] / 100 if metrics["total"] else 0)

    st.subheader("Progress by Phase")
    if df.empty:
        st.info("No backend course topics yet.")
    else:
        for phase in BACKEND_COURSE_TOPICS:
            phase_df = df[df["phase"] == phase]
            completed = int((phase_df["status"] == "Completed").sum())
            total = len(phase_df)
            progress = int(completed / total * 100) if total else 0
            st.write(f"**{phase}** - {completed}/{total} topics")
            st.progress(progress / 100)

    st.subheader("Add / Edit Topic")
    mode = st.radio("Mode", ["Edit existing topic", "Add new topic"], horizontal=True)
    selected_row = None
    if mode == "Edit existing topic" and not df.empty:
        topic_options = {
            f"{row['id']} - {row['phase']} - {row['topic']}": row["id"]
            for _, row in df.sort_values(["phase", "topic"]).iterrows()
        }
        selected_label = st.selectbox("Select topic", list(topic_options.keys()))
        selected_id = topic_options[selected_label]
        selected_row = df[df["id"] == selected_id].iloc[0]

    phase_values = list(BACKEND_COURSE_TOPICS.keys())
    status_values = ["Not Started", "In Progress", "Completed", "Revising"]

    default_phase = selected_row["phase"] if selected_row is not None else phase_values[0]
    default_status = selected_row["status"] if selected_row is not None else "Not Started"
    default_topic = selected_row["topic"] if selected_row is not None else ""
    default_started = parse_date(selected_row["date_started"], date.today()) if selected_row is not None else date.today()
    default_revision = parse_date(selected_row["revision_due_date"], date.today() + timedelta(days=7)) if selected_row is not None else date.today() + timedelta(days=7)
    default_idea = (
        selected_row["implementation_idea"]
        if selected_row is not None and selected_row["implementation_idea"]
        else IMPLEMENTATION_IDEAS.get(default_topic, "")
    )

    with st.form("backend_course_form"):
        c1, c2 = st.columns(2)
        with c1:
            date_started = st.date_input("Date started", value=default_started)
            topic = st.text_input("Topic", value=default_topic)
            subtopic = st.text_input("Subtopic", value=selected_row["subtopic"] if selected_row is not None else "")
            phase = st.selectbox("Phase", phase_values, index=phase_values.index(default_phase) if default_phase in phase_values else 0)
            source_link = st.text_input("Source link", value=selected_row["source_link"] if selected_row is not None else COURSE_LINK)
            status = st.selectbox("Status", status_values, index=status_values.index(default_status) if default_status in status_values else 0)
        with c2:
            video_done = st.checkbox("Video done", value=bool(selected_row["video_done"]) if selected_row is not None else False)
            notes_done = st.checkbox("Notes done", value=bool(selected_row["notes_done"]) if selected_row is not None else False)
            mini_implementation_done = st.checkbox(
                "Mini implementation done",
                value=bool(selected_row["mini_implementation_done"]) if selected_row is not None else False,
            )
            interview_ready = st.checkbox("Interview ready", value=bool(selected_row["interview_ready"]) if selected_row is not None else False)
            confidence = st.slider("Confidence", 1, 5, int(selected_row["confidence"]) if selected_row is not None else 1)
            revision_due_date = st.date_input("Revision due date", value=default_revision)
        key_learning = st.text_area("Key learning", value=selected_row["key_learning"] if selected_row is not None else "")
        implementation_idea = st.text_area("Implementation idea", value=default_idea)
        notes = st.text_area("Notes", value=selected_row["notes"] if selected_row is not None else "")
        submitted = st.form_submit_button("Save Topic")

    if submitted:
        if not topic.strip():
            st.error("Topic is required.")
        else:
            data = {
                "date_started": date_started,
                "topic": topic,
                "subtopic": subtopic,
                "phase": phase,
                "source_link": source_link,
                "status": status,
                "video_done": video_done,
                "notes_done": notes_done,
                "mini_implementation_done": mini_implementation_done,
                "interview_ready": interview_ready,
                "confidence": confidence,
                "key_learning": key_learning,
                "implementation_idea": implementation_idea,
                "revision_due_date": revision_due_date,
                "notes": notes,
            }
            if mode == "Edit existing topic" and selected_row is not None:
                update_row("backend_course", int(selected_row["id"]), data)
                st.success("Backend course topic updated.")
            else:
                data["created_at"] = datetime.now()
                insert_row("backend_course", data)
                st.success("Backend course topic added.")
            st.rerun()

    df = read_table("backend_course")
    st.subheader("Topic Highlights")
    if df.empty:
        st.info("No highlights yet.")
    else:
        needs_impl = df[(df["video_done"] == 1) & (df["mini_implementation_done"] == 0)]
        low_confidence = df[df["confidence"] <= 2]
        revision_due = df[pd.to_datetime(df["revision_due_date"], errors="coerce") <= pd.Timestamp(today)]

        h1, h2, h3 = st.columns(3)
        with h1:
            st.warning(f"{len(needs_impl)} watched topics need implementation.")
            show_dataframe(needs_impl[["topic", "phase", "implementation_idea"]].head(10), "All watched topics have implementation practice.")
        with h2:
            st.warning(f"{len(low_confidence)} low-confidence topics.")
            show_dataframe(low_confidence[["topic", "phase", "confidence"]].head(10), "No low-confidence topics.")
        with h3:
            st.warning(f"{len(revision_due)} topics due for revision.")
            show_dataframe(revision_due[["topic", "phase", "revision_due_date"]].head(10), "No revisions due.")

    st.subheader("Topics")
    if df.empty:
        show_dataframe(df)
        return

    f1, f2, f3, f4 = st.columns(4)
    phase_filter = f1.selectbox("Phase filter", ["All"] + phase_values)
    status_filter = f2.selectbox("Status filter", ["All"] + status_values)
    ready_filter = f3.selectbox("Interview ready filter", ["All", "Yes", "No"])
    confidence_filter = f4.selectbox("Confidence filter", ["All", "1", "2", "3", "4", "5"])

    filtered = df.copy()
    if phase_filter != "All":
        filtered = filtered[filtered["phase"] == phase_filter]
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if ready_filter != "All":
        filtered = filtered[filtered["interview_ready"] == (1 if ready_filter == "Yes" else 0)]
    if confidence_filter != "All":
        filtered = filtered[filtered["confidence"] == int(confidence_filter)]

    display_columns = [
        "id",
        "date_started",
        "phase",
        "topic",
        "subtopic",
        "status",
        "video_done",
        "notes_done",
        "mini_implementation_done",
        "interview_ready",
        "confidence",
        "implementation_idea",
        "revision_due_date",
    ]
    show_dataframe(filtered[display_columns])


def projects_page() -> None:
    st.title("Projects Tracker")
    with st.form("projects_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            project_name = st.text_input("Project name")
            category = st.selectbox("Category", ["AI Project", "Backend", "System Design", "Portfolio", "Other"])
            status = st.selectbox("Status", ["Idea", "Planning", "Building", "Testing", "Done", "Blocked"])
            progress = st.slider("Progress percentage", 0, 100, 0)
            github_link = st.text_input("GitHub link")
            demo_link = st.text_input("Demo link")
        with c2:
            current_task = st.text_area("Current task")
            next_task = st.text_area("Next task")
            blockers = st.text_area("Blockers")
            notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Project")

    if submitted:
        insert_row(
            "projects",
            {
                "project_name": project_name,
                "category": category,
                "status": status,
                "progress_percentage": progress,
                "github_link": github_link,
                "demo_link": demo_link,
                "current_task": current_task,
                "next_task": next_task,
                "blockers": blockers,
                "notes": notes,
            },
        )
        st.success("Project saved.")

    df = read_table("projects")
    if not df.empty:
        for _, row in df.iterrows():
            st.write(f"**{row['project_name']}** ({row['category']}) - {row['status']}")
            st.progress(int(row["progress_percentage"] or 0) / 100)
    show_dataframe(df)


def notes_page() -> None:
    st.title("Notes / Learnings")
    with st.form("notes_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            note_date = st.date_input("Date", value=date.today())
            category = st.selectbox("Category", ["AI", "DSA", "System Design", "Backend", "Project", "Interview", "Other"])
            title = st.text_input("Title")
        with c2:
            tags = st.text_input("Tags", placeholder="python, llm, caching")
            linked_track = st.selectbox(
                "Linked track",
                [
                    "AI Readiness Cohort",
                    "DSA using Striver A2Z Sheet",
                    "System Design",
                    "Backend Deep Dive",
                    "AI Projects",
                    "Resume + Interview Prep",
                    "Other",
                ],
            )
        content = st.text_area("Content", height=220)
        submitted = st.form_submit_button("Save Note")

    if submitted:
        insert_row(
            "notes",
            {
                "date": note_date,
                "category": category,
                "title": title,
                "content": content,
                "tags": tags,
                "linked_track": linked_track,
            },
        )
        st.success("Note saved.")

    df = read_table("notes")
    query = st.text_input("Search notes by title, content, or tags")
    if query and not df.empty:
        mask = (
            df["title"].fillna("").str.contains(query, case=False, regex=False)
            | df["content"].fillna("").str.contains(query, case=False, regex=False)
            | df["tags"].fillna("").str.contains(query, case=False, regex=False)
        )
        df = df[mask]
    show_dataframe(df)


def weekly_review_page() -> None:
    st.title("Weekly Review")
    today = date.today()
    week_start, week_end = current_week_range(today)
    backend_stats = backend_week_stats(read_table("backend_course"), week_start, week_end)
    system_design_stats = system_design_week_stats(read_table("system_design_course"), week_start, week_end)

    with st.form("weekly_review_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Week start", value=week_start)
            end = st.date_input("Week end", value=week_end)
            total_study_hours = st.number_input("Total study hours", min_value=0.0, max_value=200.0, value=0.0, step=0.5)
            dsa_count = st.number_input("DSA count", min_value=0, max_value=500, value=0)
            backend_topics_completed = st.number_input(
                "Backend topics completed this week",
                min_value=0,
                max_value=100,
                value=backend_stats["completed_this_week"],
            )
            backend_implementation_count = st.number_input(
                "Backend implementation count",
                min_value=0,
                max_value=100,
                value=backend_stats["implementation_count"],
            )
            system_design_sections_completed = st.number_input(
                "System design sections completed this week",
                min_value=0,
                max_value=25,
                value=system_design_stats["completed_this_week"],
            )
            system_design_study_hours = st.number_input(
                "System design hours spent",
                min_value=0.0,
                max_value=200.0,
                value=system_design_stats["study_hours"],
                step=0.5,
            )
            burnout_level = st.slider("Burnout level", 0, 10, 3)
        with c2:
            wins = st.text_area("Wins")
            misses = st.text_area("Misses")
            project_progress = st.text_area("Project progress")
            backend_weak_topics = st.text_area("Backend weak topics", value=backend_stats["weak_topics"])
            backend_next_week_focus = st.text_area("Backend next week focus", value=backend_stats["next_focus"])
            system_design_weak_areas = st.text_area("System design weak areas", value=system_design_stats["weak_areas"])
            system_design_next_focus = st.text_area("System design next focus", value=system_design_stats["next_focus"])
            biggest_learning = st.text_area("Biggest learning")
            next_week_focus = st.text_area("Next week focus")
        submitted = st.form_submit_button("Save Weekly Review")

    if submitted:
        insert_row(
            "weekly_reviews",
            {
                "week_start": start,
                "week_end": end,
                "wins": wins,
                "misses": misses,
                "total_study_hours": total_study_hours,
                "dsa_count": dsa_count,
                "project_progress": project_progress,
                "backend_topics_completed": backend_topics_completed,
                "backend_implementation_count": backend_implementation_count,
                "backend_weak_topics": backend_weak_topics,
                "backend_next_week_focus": backend_next_week_focus,
                "system_design_sections_completed": system_design_sections_completed,
                "system_design_study_hours": system_design_study_hours,
                "system_design_weak_areas": system_design_weak_areas,
                "system_design_next_focus": system_design_next_focus,
                "biggest_learning": biggest_learning,
                "next_week_focus": next_week_focus,
                "burnout_level": burnout_level,
                "created_at": datetime.now(),
            },
        )
        st.success("Weekly review saved.")

    show_dataframe(read_table("weekly_reviews"))


def learning_coach_agent_page() -> None:
    st.title("Learning Coach Agent")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    plans_df = read_table("learning_plans")
    dsa_summary = get_dsa_progress_summary()
    backend_summary = get_backend_course_summary()
    revision_due_items = get_revision_due_items()
    project_summary = get_project_progress_summary()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("DSA Solved", dsa_summary.get("solved", 0))
    with c2:
        metric_card("Backend Progress", f"{backend_summary.get('progress', 0)}%")
    with c3:
        metric_card("Revision Due", revision_due_items.get("total_due", 0))
    with c4:
        metric_card("Project Focus", project_summary.get("project_focus") or "No active project")

    if st.button("Generate Today's Study Plan", use_container_width=True):
        with st.spinner("Calling learning tools and generating today's plan..."):
            response = run_health_agent("learning_coach", "Generate today's study plan with Slot 1 and Slot 2.")
        st.session_state.learning_coach_last_response = response

    prompt = st.chat_input("Ask for a study plan, weak-area review, or revision plan")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling learning coach tools..."):
                response = run_health_agent("learning_coach", prompt)
            st.write(response)

    last_response = st.session_state.get("learning_coach_last_response", "")
    if last_response:
        st.subheader("Latest Generated Plan")
        st.write(last_response)

    st.subheader("Recent Learning Coach Messages")
    for message in get_recent_chat_messages("learning_coach", 8):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.subheader("Saved Learning Plans")
    show_dataframe(plans_df, "No learning plans saved yet.")

    with st.expander("Recent learning coach tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("learning_coach", 40))
        show_dataframe(logs, "No learning coach tool logs yet.")


def weekly_review_agent_page() -> None:
    st.title("Weekly Review Agent")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    default_start, default_end = current_week_range(date.today())
    c1, c2 = st.columns(2)
    with c1:
        week_start = st.date_input("Week start", value=default_start, key="weekly_ai_start")
    with c2:
        week_end = st.date_input("Week end", value=default_end, key="weekly_ai_end")

    reviews_df = read_table("weekly_ai_reviews")
    consistency_summary = calculate_weekly_consistency_score()
    burnout_summary = calculate_burnout_risk()

    m1, m2, m3 = st.columns(3)
    with m1:
        metric_card("Consistency Score", consistency_summary.get("consistency_score", 0))
    with m2:
        metric_card("Burnout Risk", burnout_summary.get("burnout_risk", "Low"))
    with m3:
        metric_card("Risk Reasons", ", ".join(burnout_summary.get("reasons", [])) or "None")

    if st.button("Generate Weekly Review", use_container_width=True):
        prompt = f"Generate weekly review for {week_start.isoformat()} to {week_end.isoformat()}."
        with st.spinner("Calling weekly review tools and generating review..."):
            response = run_health_agent("weekly_review", prompt)
        st.session_state.weekly_review_last_response = response

    prompt = st.chat_input("Ask for a weekly review, burnout check, or next-week focus")
    if prompt:
        full_prompt = f"{prompt}\nWeek range: {week_start.isoformat()} to {week_end.isoformat()}."
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling weekly review tools..."):
                response = run_health_agent("weekly_review", full_prompt)
            st.write(response)

    last_response = st.session_state.get("weekly_review_last_response", "")
    if last_response:
        st.subheader("Latest Generated Review")
        st.write(last_response)

    st.subheader("Recent Weekly Review Messages")
    for message in get_recent_chat_messages("weekly_review", 8):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.subheader("Saved Weekly AI Reviews")
    show_dataframe(reviews_df, "No weekly AI reviews saved yet.")

    with st.expander("Recent weekly review tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("weekly_review", 50))
        show_dataframe(logs, "No weekly review tool logs yet.")


def health_dashboard_page() -> None:
    st.title("Health Dashboard")
    profile = get_fitness_profile()
    gym_df = read_table("gym_sessions")
    diet_df = read_table("diet_logs")
    weight_df = read_table("weight_logs")
    reports_df = read_table("health_reports")
    today = date.today()
    week_start, week_end = current_week_range(today)

    latest_weight = float(weight_df.iloc[0]["weight_kg"]) if not weight_df.empty and weight_df.iloc[0]["weight_kg"] else 0
    start_weight = float(profile.get("starting_weight_kg") or 0)
    goal_weight = float(profile.get("goal_weight_kg") or 0)
    if not latest_weight:
        latest_weight = start_weight
    total_loss_needed = max(start_weight - goal_weight, 0.1)
    current_loss = max(start_weight - latest_weight, 0)
    goal_progress = min(int(current_loss / total_loss_needed * 100), 100)

    if not gym_df.empty:
        gym_dates = pd.to_datetime(gym_df["session_date"], errors="coerce")
        gym_week = gym_df[(gym_dates >= pd.Timestamp(week_start)) & (gym_dates <= pd.Timestamp(week_end))]
    else:
        gym_week = pd.DataFrame()

    if not weight_df.empty:
        steps_avg = int(weight_df["steps"].fillna(0).tail(7).mean())
    else:
        steps_avg = int(gym_df["steps"].fillna(0).tail(7).mean()) if not gym_df.empty else 0

    split_matches = 0
    if not gym_week.empty:
        for _, row in gym_week.iterrows():
            planned = WEEKLY_SPLIT.get(row["day"], "").lower()
            actual = str(row["session_type"]).lower()
            if actual and (actual in planned or planned in actual):
                split_matches += 1
    split_adherence = int(split_matches / len(gym_week) * 100) if not gym_week.empty else 0

    latest_gym_analysis = ""
    if not gym_df.empty and "analysis" in gym_df.columns:
        analyzed = gym_df[gym_df["analysis"].fillna("") != ""]
        if not analyzed.empty:
            latest_gym_analysis = analyzed.sort_values(["session_date", "id"]).iloc[-1]["analysis"]
    latest_gym_analysis = latest_gym_analysis or get_latest_bot_message("gym")
    latest_diet_analysis = get_latest_bot_message("diet")
    latest_recommendation = ""
    latest_health_score = 0
    if not reports_df.empty:
        latest_report = reports_df.sort_values(["date", "id"]).iloc[-1]
        latest_health_score = int(float(latest_report.get("health_score", 0) or 0))
        latest_recommendation = str(latest_report.get("recommendations", "") or "")

    workout_summary = calculate_weekly_workout_count()
    protein_summary = calculate_weekly_avg_protein()
    weight_trend = calculate_weight_trend()
    if not latest_health_score:
        latest_health_score = int(calculate_health_score().get("health_score", 0))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Latest Weight", f"{latest_weight:.1f} kg")
    with c2:
        metric_card("Goal Progress", f"{goal_progress}%")
    with c3:
        metric_card("Gym Sessions This Week", len(gym_week))
    with c4:
        metric_card("Split Adherence", f"{split_adherence}%")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Volume This Week", int(gym_week["total_volume_kg"].sum()) if not gym_week.empty else 0)
    with c2:
        metric_card("Cardio Minutes", int(gym_week["cardio_minutes"].sum()) if not gym_week.empty else 0)
    with c3:
        metric_card("Steps Average", steps_avg)
    with c4:
        metric_card("Diet Logs", len(diet_df))

    st.subheader("Health Manager")
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        metric_card("Latest Health Score", latest_health_score)
    with h2:
        metric_card("Weekly Workouts", workout_summary.get("workout_count", 0))
    with h3:
        metric_card("Avg Protein", f"{protein_summary.get('avg_protein_g', 0):.0f} g")
    with h4:
        metric_card("Weight Trend", weight_trend.get("trend", "not enough data"))
    st.caption(latest_recommendation or "Generate a Health Manager Agent report to see the latest recommendation here.")

    if not diet_df.empty:
        latest_diet = diet_df.sort_values(["log_date", "id"]).iloc[-1]
        avg_deficit = (
            round(float(diet_df["estimated_deficit_calories"].fillna(0).tail(7).mean()), 1)
            if "estimated_deficit_calories" in diet_df.columns
            else 0
        )
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            metric_card("Latest Calories", int(latest_diet["calories"] or 0))
        with d2:
            metric_card("Latest Protein", f"{float(latest_diet['protein_g'] or 0):.0f} g")
        with d3:
            metric_card("Latest Deficit", int(latest_diet.get("estimated_deficit_calories", 0) or 0))
        with d4:
            metric_card("7 Log Avg Deficit", avg_deficit)

    st.subheader("Nutrition Targets")
    n1, n2, n3, n4 = st.columns(4)
    with n1:
        metric_card("Protein Target", f"{profile.get('target_protein_range', '130-150')} g")
    with n2:
        metric_card("Calories Target", profile.get("target_calories", "Set in profile"))
    with n3:
        metric_card("Water Target", f"{profile.get('water_target_liters', 4)} L")
    with n4:
        metric_card("Diet Type", profile.get("diet_type", "Eggetarian"))

    st.subheader("Weight Goal")
    st.progress(goal_progress / 100)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Gym Volume")
        if gym_df.empty:
            st.info("No gym sessions yet.")
        else:
            chart_df = gym_df.sort_values("session_date")
            st.plotly_chart(px.bar(chart_df, x="session_date", y="total_volume_kg", color="session_type"), use_container_width=True)
    with c2:
        st.subheader("Weight & Steps")
        if weight_df.empty:
            st.info("No weight logs yet.")
        else:
            chart_df = weight_df.sort_values("log_date")
            st.plotly_chart(px.line(chart_df, x="log_date", y=["weight_kg", "steps"]), use_container_width=True)

    st.subheader("Diet Trends")
    if diet_df.empty:
        st.info("No diet logs yet.")
    else:
        diet_chart_df = diet_df.copy()
        diet_chart_df["log_date_dt"] = pd.to_datetime(diet_chart_df["log_date"], errors="coerce")
        diet_chart_df = diet_chart_df.sort_values(["log_date_dt", "id"])
        if "estimated_deficit_calories" not in diet_chart_df.columns:
            diet_chart_df["estimated_deficit_calories"] = 0
        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(
                diet_chart_df,
                x="log_date",
                y=["calories", "estimated_deficit_calories"],
                markers=True,
                title="Calories & Deficit",
            )
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(
                diet_chart_df,
                x="log_date",
                y="protein_g",
                markers=True,
                title="Protein Intake",
            )
            fig.add_hrect(y0=130, y1=150, opacity=0.15, line_width=0, annotation_text="Target")
            st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Latest Gym Coach Analysis")
        st.write(latest_gym_analysis or "No gym coach analysis yet.")
    with c2:
        st.subheader("Latest Diet Coach Analysis")
        st.write(latest_diet_analysis or "No diet coach analysis yet.")


def get_latest_bot_message(bot_type: str) -> str:
    messages = get_recent_chat_messages(bot_type, 20)
    for message in reversed(messages):
        if message["role"] == "assistant":
            return message["content"]
    return ""


def gym_tracker_page() -> None:
    st.title("Gym Tracker")
    with st.form("manual_gym_session_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            session_date = date.today()
            st.text_input("Session date", value=session_date.isoformat(), disabled=True)
            st.text_input("Day", value=session_date.strftime("%A"), disabled=True)
            session_type = st.selectbox("Session type", list(set(WEEKLY_SPLIT.values())) + ["Other"], key="manual_gym_type")
        with c2:
            duration = st.number_input("Duration minutes", min_value=0, max_value=300, value=60)
            volume = st.number_input("Total volume kg", min_value=0.0, max_value=100000.0, value=0.0, step=50.0)
            sets = st.number_input("Set count", min_value=0, max_value=200, value=0)
        with c3:
            exercises = st.number_input("Exercise count", min_value=0, max_value=50, value=0)
            cardio = st.number_input("Cardio minutes", min_value=0, max_value=300, value=0)
            steps = st.number_input("Steps", min_value=0, max_value=50000, value=0)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Gym Session")

    if submitted:
        save_gym_session(
            {
                "session_date": session_date.isoformat(),
                "day": session_date.strftime("%A"),
                "session_type": session_type,
                "title": session_type,
                "duration_minutes": duration,
                "total_volume_kg": volume,
                "exercise_count": exercises,
                "set_count": sets,
                "cardio_minutes": cardio,
                "cardio_distance_km": 0,
                "steps": steps,
                "raw_text": notes,
                "exercises": [],
            }
        )
        st.success("Gym session saved.")

    df = read_table("gym_sessions")
    if not df.empty:
        chart_df = df.copy()
        chart_df["session_date_dt"] = pd.to_datetime(chart_df["session_date"], errors="coerce")
        chart_df = chart_df.sort_values(["session_date_dt", "id"])
        chart_df["volume_per_minute"] = chart_df.apply(
            lambda row: round(row["total_volume_kg"] / row["duration_minutes"], 1)
            if row["duration_minutes"]
            else 0,
            axis=1,
        )
        chart_df["sets_per_minute"] = chart_df.apply(
            lambda row: round(row["set_count"] / row["duration_minutes"], 2)
            if row["duration_minutes"]
            else 0,
            axis=1,
        )

        st.subheader("Gym Analytics")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(
                chart_df,
                x="session_date",
                y="total_volume_kg",
                color="session_type",
                markers=True,
                title="Total Volume Trend",
            )
            fig.update_layout(yaxis_title="Volume (kg)", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(
                chart_df,
                x="session_date",
                y="duration_minutes",
                color="session_type",
                markers=True,
                title="Workout Duration Trend",
            )
            fig.update_layout(yaxis_title="Minutes", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(
                chart_df,
                x="session_date",
                y="set_count",
                color="session_type",
                markers=True,
                title="Set Count Trend",
            )
            fig.update_layout(yaxis_title="Sets", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(
                chart_df,
                x="session_date",
                y="volume_per_minute",
                color="session_type",
                markers=True,
                title="Training Density Trend",
            )
            fig.update_layout(yaxis_title="Kg per minute", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(
                chart_df,
                x="session_date",
                y="cardio_minutes",
                color="session_type",
                markers=True,
                title="Cardio Minutes Trend",
            )
            fig.update_layout(yaxis_title="Minutes", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(
                chart_df,
                x="session_date",
                y="steps",
                color="session_type",
                markers=True,
                title="Steps Trend",
            )
            fig.update_layout(yaxis_title="Steps", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True)

        fig = px.line(
            chart_df,
            x="session_date",
            y=["total_volume_kg", "set_count", "duration_minutes"],
            markers=True,
            title="Combined Workload Trend",
        )
        fig.update_layout(xaxis_title="Date", yaxis_title="Value")
        st.plotly_chart(fig, use_container_width=True)
    show_dataframe(df)


def gym_coach_bot_page() -> None:
    st.title("Gym Coach Bot")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    for message in get_recent_chat_messages("gym", 10):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Paste Lyfta workout text for analysis")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling gym tools and analyzing workout..."):
                response = run_health_agent("gym", prompt)
            st.write(response)

    with st.expander("Recent gym bot tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("gym", 30))
        show_dataframe(logs, "No gym tool logs yet.")


def diet_tracker_page() -> None:
    st.title("Diet Tracker")
    with st.form("manual_diet_log_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            log_date = st.date_input("Log date", value=date.today(), key="manual_diet_date")
            calories = st.number_input("Calories", min_value=0, max_value=10000, value=0)
        with c2:
            protein = st.number_input("Protein g", min_value=0.0, max_value=400.0, value=0.0)
            carbs = st.number_input("Carbs g", min_value=0.0, max_value=800.0, value=0.0)
        with c3:
            fat = st.number_input("Fat g", min_value=0.0, max_value=300.0, value=0.0)
            estimated_deficit = st.number_input("Estimated deficit calories", min_value=0, max_value=3000, value=0)
        with c4:
            meal_quality = st.selectbox("Meal quality", ["High protein", "Balanced", "Needs more protein", "Too calorie dense"])
            raw_text = st.text_area("Meals")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Diet Log")

    if submitted:
        save_diet_log(
            {
                "log_date": log_date.isoformat(),
                "raw_text": raw_text,
                "calories": calories,
                "protein_g": protein,
                "carbs_g": carbs,
                "fat_g": fat,
                "estimated_deficit_calories": estimated_deficit,
                "meal_quality": meal_quality,
                "notes": notes,
            }
        )
        st.success("Diet log saved.")

    df = read_table("diet_logs")
    if not df.empty:
        chart_df = df.copy()
        chart_df["log_date_dt"] = pd.to_datetime(chart_df["log_date"], errors="coerce")
        chart_df = chart_df.sort_values(["log_date_dt", "id"])
        if "estimated_deficit_calories" not in chart_df.columns:
            chart_df["estimated_deficit_calories"] = 0

        st.subheader("Diet Analytics")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(chart_df, x="log_date", y="calories", markers=True, title="Calories Trend")
            fig.add_hline(y=2200, line_dash="dot", annotation_text="Lower training target")
            fig.add_hline(y=2400, line_dash="dot", annotation_text="Upper training target")
            fig.update_layout(xaxis_title="Date", yaxis_title="Calories")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(chart_df, x="log_date", y="estimated_deficit_calories", markers=True, title="Calorie Deficit Trend")
            fig.update_layout(xaxis_title="Date", yaxis_title="Estimated deficit")
            st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(chart_df, x="log_date", y="protein_g", markers=True, title="Protein Trend")
            fig.add_hrect(y0=130, y1=150, opacity=0.15, line_width=0, annotation_text="Protein target")
            fig.update_layout(xaxis_title="Date", yaxis_title="Protein (g)")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(chart_df, x="log_date", y=["carbs_g", "fat_g"], markers=True, title="Carbs & Fat Trend")
            fig.update_layout(xaxis_title="Date", yaxis_title="Grams")
            st.plotly_chart(fig, use_container_width=True)

        chart_df["week_start"] = chart_df["log_date_dt"].dt.to_period("W").apply(lambda period: period.start_time)
        weekly_df = (
            chart_df.groupby("week_start", as_index=False)
            .agg(
                calories=("calories", "mean"),
                protein_g=("protein_g", "mean"),
                estimated_deficit_calories=("estimated_deficit_calories", "sum"),
            )
            .sort_values("week_start")
        )
        fig = px.line(
            weekly_df,
            x="week_start",
            y=["calories", "protein_g", "estimated_deficit_calories"],
            markers=True,
            title="Weekly Nutrition Trend",
        )
        fig.update_layout(xaxis_title="Week", yaxis_title="Value")
        st.plotly_chart(fig, use_container_width=True)
    show_dataframe(df)


def diet_coach_bot_page() -> None:
    st.title("Diet Coach Bot")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    for message in get_recent_chat_messages("diet", 10):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Enter today's meals in natural language")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Estimating macros and calling diet tools..."):
                response = run_health_agent("diet", prompt)
            st.write(response)

    with st.expander("Recent diet bot tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("diet", 30))
        show_dataframe(logs, "No diet tool logs yet.")


def health_manager_agent_page() -> None:
    st.title("Health Manager Agent")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    reports_df = read_table("health_reports")
    score_summary = calculate_health_score()
    workout_summary = calculate_weekly_workout_count()
    protein_summary = calculate_weekly_avg_protein()
    weight_summary = calculate_weight_trend()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Health Score", score_summary.get("health_score", 0))
    with c2:
        metric_card("Weekly Workouts", workout_summary.get("workout_count", 0))
    with c3:
        metric_card("Avg Protein", f"{protein_summary.get('avg_protein_g', 0):.0f} g")
    with c4:
        metric_card("Weight Trend", weight_summary.get("trend", "not enough data"))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Generate Daily Report", use_container_width=True):
            with st.spinner("Calling health tools and generating daily report..."):
                response = run_health_agent("health_manager", "Generate today's daily health report.")
            st.session_state.health_manager_last_response = response
    with c2:
        if st.button("Generate Weekly Report", use_container_width=True):
            with st.spinner("Calling health tools and generating weekly report..."):
                response = run_health_agent("health_manager", "Generate this week's health report.")
            st.session_state.health_manager_last_response = response

    prompt = st.chat_input("Ask for a health report or risk review")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling health manager tools..."):
                response = run_health_agent("health_manager", prompt)
            st.write(response)

    last_response = st.session_state.get("health_manager_last_response", "")
    if last_response:
        st.subheader("Latest Generated Report")
        st.write(last_response)

    st.subheader("Recent Health Manager Messages")
    for message in get_recent_chat_messages("health_manager", 8):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.subheader("Saved Health Reports")
    show_dataframe(reports_df, "No health reports saved yet.")

    with st.expander("Recent health manager tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("health_manager", 40))
        show_dataframe(logs, "No health manager tool logs yet.")


def weight_steps_tracker_page() -> None:
    st.title("Weight & Steps Tracker")
    with st.form("weight_steps_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            log_date = st.date_input("Log date", value=date.today(), key="weight_steps_date")
        with c2:
            weight = st.number_input("Weight kg", min_value=0.0, max_value=300.0, value=0.0, step=0.1)
        with c3:
            steps = st.number_input("Steps", min_value=0, max_value=50000, value=0)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Weight / Steps")

    if submitted:
        save_weight_log({"log_date": log_date.isoformat(), "weight_kg": weight, "steps": steps, "notes": notes})
        st.success("Weight and steps log saved.")

    df = read_table("weight_logs")
    if not df.empty:
        chart_df = df.sort_values("log_date")
        st.plotly_chart(px.line(chart_df, x="log_date", y="weight_kg", markers=True), use_container_width=True)
        st.plotly_chart(px.bar(chart_df, x="log_date", y="steps"), use_container_width=True)
    show_dataframe(df)


def export_page() -> None:
    st.title("Export Data")
    st.write("Download individual CSV files or export the full tracker as one Excel workbook.")

    for table in TABLES:
        df = read_table(table)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Download {table}.csv",
            data=csv,
            file_name=f"{table}.csv",
            mime="text/csv",
            key=f"csv_{table}",
        )

    try:
        import openpyxl  # noqa: F401

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for table in TABLES:
                read_table(table).to_excel(writer, sheet_name=table[:31], index=False)
        st.download_button(
            "Download all data as Excel",
            data=output.getvalue(),
            file_name="study_tracker_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except ImportError:
        st.warning("Install openpyxl to enable Excel export. CSV export is available now.")


PAGES = {
    "Dashboard": dashboard,
    "Daily Log": daily_log_page,
    "DSA Tracker": dsa_tracker_page,
    "AI Cohort Tracker": ai_cohort_page,
    "System Design Tracker": system_design_page,
    "System Design Course Tracker": system_design_course_page,
    "Backend Deep Dive": backend_page,
    "Backend Course Tracker": backend_course_page,
    "Projects Tracker": projects_page,
    "Notes / Learnings": notes_page,
    "Weekly Review": weekly_review_page,
    "Weekly Review Agent": weekly_review_agent_page,
    "Learning Coach Agent": learning_coach_agent_page,
    "Export Data": export_page,
    "Health Dashboard": health_dashboard_page,
    "Health Manager Agent": health_manager_agent_page,
    "Gym Tracker": gym_tracker_page,
    "Gym Coach Bot": gym_coach_bot_page,
    "Diet Tracker": diet_tracker_page,
    "Diet Coach Bot": diet_coach_bot_page,
    "Weight & Steps Tracker": weight_steps_tracker_page,
}

STUDY_PAGES = [
    "Dashboard",
    "Daily Log",
    "DSA Tracker",
    "AI Cohort Tracker",
    "System Design Tracker",
    "System Design Course Tracker",
    "Backend Deep Dive",
    "Backend Course Tracker",
    "Projects Tracker",
    "Notes / Learnings",
    "Weekly Review",
    "Weekly Review Agent",
    "Learning Coach Agent",
    "Export Data",
]

HEALTH_PAGES = [
    "Health Dashboard",
    "Health Manager Agent",
    "Gym Tracker",
    "Gym Coach Bot",
    "Diet Tracker",
    "Diet Coach Bot",
    "Weight & Steps Tracker",
]


def set_current_page(page_name: str) -> None:
    st.session_state.current_page = page_name


def configure_openai_key() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return

    try:
        secret_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        secret_key = ""

    if secret_key:
        os.environ["OPENAI_API_KEY"] = secret_key


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")
    configure_openai_key()
    init_db()
    initialize_health_tables()

    st.sidebar.title(APP_NAME)
    st.sidebar.subheader("Study Timetable & Projects")
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"
    for page_name in STUDY_PAGES:
        st.sidebar.button(
            page_name,
            key=f"nav_study_{page_name}",
            use_container_width=True,
            type="primary" if st.session_state.current_page == page_name else "secondary",
            on_click=set_current_page,
            args=(page_name,),
        )

    st.sidebar.divider()
    st.sidebar.subheader("Gym & Diet")
    for page_name in HEALTH_PAGES:
        st.sidebar.button(
            page_name,
            key=f"nav_health_{page_name}",
            use_container_width=True,
            type="primary" if st.session_state.current_page == page_name else "secondary",
            on_click=set_current_page,
            args=(page_name,),
        )

    page = st.session_state.current_page
    st.sidebar.divider()
    st.sidebar.caption(f"Database: {DB_PATH}")

    PAGES[page]()


if __name__ == "__main__":
    main()
