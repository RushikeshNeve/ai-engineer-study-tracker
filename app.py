from __future__ import annotations

import io
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI

from openai_agent import run_health_agent
from services.voice_mode import (
    generate_voice_response,
    get_voice_settings,
    handle_voice_input,
    initialize_voice_tables,
    save_audio_response,
    save_voice_conversation as persist_voice_conversation,
    update_voice_settings,
)
from services.mythos_personality import get_voice_personality_prompt
from services.memory_service import (
    autosave_memories,
    delete_memory,
    get_all_memories,
    initialize_memory_tables,
    save_memory,
    search_memory,
    update_memory,
)
from services.automation_engine import (
    get_latest_daily_briefing,
    initialize_automation_tables,
    latest_notifications,
    latest_reports,
    list_automation_logs,
    list_automations,
    list_notifications,
    mark_notification_read,
    run_automation,
    update_automation_enabled,
)
from services.github_service import (
    get_repository_details as github_repository_details,
    github_activity_trend,
    github_is_configured,
    github_weekly_summary,
    initialize_github_tables,
    link_github_to_projects,
    list_recent_activity as list_github_recent_activity,
    list_saved_repositories,
    sync_github_activity,
)
from services.observability_service import (
    daily_metric,
    initialize_observability_tables,
    log_llm_request,
    log_router_execution,
    observability_dashboard_summary,
    read_observability_table,
    top_counts,
)
from services.scheduler_service import tick as scheduler_tick
from tools import (
    WEEKLY_SPLIT,
    calculate_health_score,
    calculate_weekly_avg_protein,
    calculate_weekly_workout_count,
    calculate_weight_trend,
    calculate_burnout_risk,
    calculate_weekly_consistency_score,
    get_backend_course_summary,
    get_backend_readiness,
    get_dsa_interview_readiness,
    get_dsa_progress_summary,
    get_fitness_profile,
    get_project_progress_summary,
    get_project_portfolio_summary,
    get_recent_chat_messages,
    get_recent_diet_logs,
    get_recent_gym_sessions,
    get_recent_tool_logs,
    get_revision_due_items,
    get_system_design_readiness,
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
    "interview_sessions",
    "project_plans",
    "knowledge_artifacts",
    "unified_chat_messages",
    "voice_conversations",
    "voice_settings",
    "user_memories",
    "memory_embeddings",
    "automations",
    "automation_logs",
    "notifications",
    "daily_briefings",
    "github_repositories",
    "github_activity",
    "agent_executions",
    "tool_executions",
    "router_executions",
    "llm_requests",
    "memory_retrievals",
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

            CREATE TABLE IF NOT EXISTS interview_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                interview_type TEXT,
                topic TEXT,
                questions TEXT,
                user_answers TEXT,
                feedback TEXT,
                score REAL DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS project_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                plan_type TEXT,
                roadmap TEXT,
                next_tasks TEXT,
                architecture_notes TEXT,
                risks TEXT,
                resume_angle TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_type TEXT,
                source_type TEXT,
                source_id INTEGER,
                title TEXT,
                content TEXT,
                tags TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS unified_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                selected_agent TEXT,
                confidence REAL DEFAULT 0,
                created_at TEXT
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

            CREATE TABLE IF NOT EXISTS github_repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT UNIQUE,
                repo_url TEXT,
                description TEXT,
                language TEXT,
                stars INTEGER DEFAULT 0,
                forks INTEGER DEFAULT 0,
                last_pushed_at TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS github_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                activity_type TEXT,
                title TEXT,
                url TEXT,
                activity_date TEXT,
                metadata_json TEXT,
                created_at TEXT
            );

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
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_github_activity_unique "
            "ON github_activity(repo_name, activity_type, url)"
        )
        ensure_weekly_backend_columns(conn)
        ensure_weekly_system_design_columns(conn)
        preload_backend_course(conn)
        preload_system_design_course(conn)
        ensure_voice_conversation_columns(conn)
    initialize_memory_tables()
    initialize_automation_tables()
    initialize_github_tables()
    initialize_observability_tables()
    initialize_voice_tables()


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


AGENT_REGISTRY = {
    "gym_coach": {
        "agent_id": "gym_coach",
        "name": "Gym Coach Agent",
        "description": "Analyzes workouts, Lyfta logs, progressive overload, gym split, cardio, steps, and recovery.",
        "capabilities": ["workout analysis", "Lyfta workout parsing", "progressive overload", "gym split adherence", "save gym sessions"],
        "example_prompts": ["Analyze today's workout", "Compare my push workout with last week", "Save this Lyfta workout"],
        "bot_type": "gym",
    },
    "diet_coach": {
        "agent_id": "diet_coach",
        "name": "Diet Coach Agent",
        "description": "Analyzes meals, calories, protein, macros, calorie deficit, and fat-loss suitability.",
        "capabilities": ["meal analysis", "macro estimates", "protein target", "calorie deficit", "save diet logs"],
        "example_prompts": ["Analyze today's diet", "Did I hit protein target?", "Save my meals"],
        "bot_type": "diet",
    },
    "health_manager": {
        "agent_id": "health_manager",
        "name": "Health Manager Agent",
        "description": "Creates daily and weekly health reports across gym, diet, weight, steps, recovery, and health score.",
        "capabilities": ["health report", "weight trend", "steps", "recovery", "health score", "weekly health summary"],
        "example_prompts": ["Generate my daily health report", "How is my recovery?", "Check my health score"],
        "bot_type": "health_manager",
    },
    "learning_coach": {
        "agent_id": "learning_coach",
        "name": "Learning Coach Agent",
        "description": "Plans daily study and balances DSA, backend, system design, AI cohort, projects, and revisions.",
        "capabilities": ["daily study plan", "DSA planning", "backend learning", "system design", "weak areas", "revision due"],
        "example_prompts": ["What should I study today?", "Create today's study plan", "What are my weak areas?"],
        "bot_type": "learning_coach",
    },
    "weekly_review": {
        "agent_id": "weekly_review",
        "name": "Weekly Review Agent",
        "description": "Reviews the full week across study, coding, GitHub, gym, diet, consistency, burnout risk, wins, misses, and next focus.",
        "capabilities": ["weekly review", "github activity", "coding activity", "burnout risk", "weekly score", "wins and misses", "next week focus"],
        "example_prompts": ["Generate this week's review", "Summarize my GitHub activity this week", "What did I miss this week?", "Plan next week"],
        "bot_type": "weekly_review",
    },
    "resume_interview": {
        "agent_id": "resume_interview",
        "name": "Resume & Interview Coach Agent",
        "description": "Assesses interview readiness, GitHub proof of work, resume bullets, mock interview questions, DSA, backend, system design, and project stories.",
        "capabilities": ["resume bullets", "github proof", "coding activity", "mock interview", "interview readiness", "project storytelling", "SDE2 prep"],
        "example_prompts": ["Generate resume bullets", "Use GitHub activity for my resume", "Give me mock interview questions", "Assess my interview readiness"],
        "bot_type": "resume_interview",
    },
    "project_mentor": {
        "agent_id": "project_mentor",
        "name": "Project Mentor Agent",
        "description": "Creates project roadmaps, next tasks, README improvements, architecture notes, risks, resume positioning, and GitHub activity analysis.",
        "capabilities": ["project roadmap", "github", "commits", "repository", "pull request", "next tasks", "README", "architecture", "portfolio gaps", "resume angle"],
        "example_prompts": ["Create a roadmap for my project", "Analyze my GitHub project activity", "What should I build next?", "Improve my README"],
        "bot_type": "project_mentor",
    },
    "knowledge_assistant": {
        "agent_id": "knowledge_assistant",
        "name": "Notes & Knowledge Assistant Agent",
        "description": "Searches notes, summarizes knowledge, creates flashcards, revision questions, and connects concepts across tracks.",
        "capabilities": ["search notes", "summarize notes", "flashcards", "revision questions", "knowledge artifacts"],
        "example_prompts": ["Summarize my JWT notes", "Create flashcards", "Generate revision questions for indexing"],
        "bot_type": "knowledge_assistant",
    },
}


ROUTER_KEYWORDS = {
    "gym_coach": ["workout", "lyfta", "push", "pull", "legs", "sets", "reps", "volume", "cardio", "gym", "split"],
    "diet_coach": ["diet", "meal", "protein", "calories", "calorie", "macros", "fat loss", "deficit", "breakfast", "lunch", "dinner"],
    "health_manager": ["health", "weight", "steps", "recovery", "health score", "daily health", "weekly health"],
    "learning_coach": ["study", "dsa", "backend", "system design", "ai cohort", "revision", "weak areas", "plan today"],
    "weekly_review": ["weekly review", "this week", "next week", "burnout", "wins", "misses", "consistency", "github activity"],
    "resume_interview": ["resume", "interview", "mock", "readiness", "sde2", "questions", "job", "github", "commit"],
    "project_mentor": ["project", "roadmap", "readme", "portfolio", "architecture", "milestone", "tasks", "github", "repo", "repository", "commit", "pull request", "pr"],
    "knowledge_assistant": ["notes", "note", "flashcard", "summarize", "knowledge", "revise", "revision questions"],
}


for agent_config in AGENT_REGISTRY.values():
    agent_config["run_function"] = run_health_agent


def agent_search_text(agent: dict) -> str:
    return " ".join([agent["name"], agent["description"], " ".join(agent["capabilities"]), " ".join(agent["example_prompts"])]).lower()


def rank_agents_rule_based(prompt: str) -> list[dict]:
    prompt_lower = prompt.lower()
    prompt_terms = {term for term in re.split(r"[^a-z0-9+#.]+", prompt_lower) if len(term) > 2}
    ranked = []
    for agent_id, agent in AGENT_REGISTRY.items():
        search_text = agent_search_text(agent)
        score = 0.0
        for term in prompt_terms:
            if term in search_text:
                score += 1.0
        for phrase in ROUTER_KEYWORDS.get(agent_id, []):
            if phrase in prompt_lower:
                score += 3.0 if " " in phrase else 1.8
        for example in agent["example_prompts"]:
            example_terms = {term for term in re.split(r"[^a-z0-9+#.]+", example.lower()) if len(term) > 2}
            score += len(prompt_terms & example_terms) * 0.7
        ranked.append({"agent_id": agent_id, "name": agent["name"], "score": round(score, 2), "confidence": 0.0, "reason": "Rule-based match against description, capabilities, examples, and keywords."})

    ranked = sorted(ranked, key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item["confidence"] = round(min(item["score"] / 12, 1), 2)
    return ranked


def openai_route_agent(prompt: str) -> dict | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    router_agents = [
        {
            "agent_id": agent_id,
            "name": agent["name"],
            "description": agent["description"],
            "capabilities": agent["capabilities"],
            "example_prompts": agent["example_prompts"],
        }
        for agent_id, agent in AGENT_REGISTRY.items()
    ]
    try:
        client = OpenAI()
        started = datetime.now()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_ROUTER_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
            messages=[
                {"role": "system", "content": "Route the user prompt to exactly one agent. Return only JSON with selected_agent, confidence, and reason."},
                {"role": "user", "content": json.dumps({"prompt": prompt, "agents": router_agents})},
            ],
            response_format={"type": "json_object"},
        )
        elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        usage = getattr(response, "usage", None)
        if usage:
            log_llm_request(
                response.model or os.getenv("OPENAI_ROUTER_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
                getattr(usage, "prompt_tokens", 0) or 0,
                getattr(usage, "completion_tokens", 0) or 0,
                getattr(usage, "total_tokens", 0) or 0,
                elapsed_ms,
            )
        parsed = json.loads(response.choices[0].message.content or "{}")
        if parsed.get("selected_agent") in AGENT_REGISTRY:
            return {"agent_id": parsed.get("selected_agent"), "confidence": float(parsed.get("confidence", 0) or 0), "reason": parsed.get("reason", "OpenAI router classification.")}
    except Exception:
        return None
    return None


def route_command_center_prompt(prompt: str) -> dict:
    started = datetime.now()
    ranked = rank_agents_rule_based(prompt)
    selected = ranked[0]["agent_id"] if ranked else "learning_coach"
    confidence = ranked[0]["confidence"] if ranked else 0.0
    reason = ranked[0]["reason"] if ranked else "No strong rule-based match."
    router_result = openai_route_agent(prompt)
    if router_result and router_result["confidence"] >= 0.55:
        selected = router_result["agent_id"]
        confidence = round(router_result["confidence"], 2)
        reason = router_result["reason"]
        for item in ranked:
            if item["agent_id"] == selected:
                item["confidence"] = max(item["confidence"], confidence)
                item["reason"] = reason
        ranked = sorted(ranked, key=lambda item: item["confidence"], reverse=True)

    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    log_router_execution(prompt, selected, confidence, elapsed_ms)
    return {"selected_agent": selected, "confidence": confidence, "reason": reason, "ranked_agents": ranked[:3], "ambiguous": confidence < 0.3}


def select_command_center_agents(routing: dict) -> list[str]:
    ranked = routing.get("ranked_agents", [])
    if routing.get("ambiguous"):
        return []

    selected = routing["selected_agent"]
    selected_agents = [selected]
    for item in ranked:
        agent_id = item["agent_id"]
        if agent_id == selected:
            continue
        if item.get("confidence", 0) >= 0.45 and item.get("score", 0) >= 5:
            selected_agents.append(agent_id)
        if len(selected_agents) >= 3:
            break
    return selected_agents


def run_command_center_agents(prompt: str, agent_ids: list[str], context_prefix: str = "") -> str:
    responses = []
    agent_prompt = f"{context_prefix}\n\nUser request: {prompt}" if context_prefix else prompt
    for agent_id in agent_ids:
        agent = AGENT_REGISTRY[agent_id]
        response = agent["run_function"](agent["bot_type"], agent_prompt)
        if response:
            responses.append(response)
    if not responses:
        return "I need a little more context before I can help. Do you mean food, workout, study, projects, notes, or interview prep?"
    if len(responses) == 1:
        return responses[0]
    return "\n\n".join(responses)


def execute_command_center_prompt(prompt: str, context_prefix: str = "") -> tuple[str, dict]:
    routing = route_command_center_prompt(prompt)
    agent_ids = select_command_center_agents(routing)
    selected_agents_value = ",".join(agent_ids) if agent_ids else ""
    save_unified_chat_message("user", prompt, selected_agents_value, routing["confidence"])
    if not agent_ids:
        response = "Do you want me to help with food, workout, study, projects, notes, or interview prep?"
    else:
        response = run_command_center_agents(prompt, agent_ids, context_prefix)
    autosave_memories(prompt, response, source="mythos")
    save_unified_chat_message("assistant", response, selected_agents_value, routing["confidence"])
    return response, routing


def save_unified_chat_message(role: str, content: str, selected_agent: str = "", confidence: float = 0.0) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO unified_chat_messages (role, content, selected_agent, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (role, content, selected_agent, confidence, datetime.now().isoformat()),
        )


def get_recent_unified_chat(limit: int = 12) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM unified_chat_messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return list(reversed([dict(row) for row in rows]))


def mythos_startup_greeting(now: datetime | None = None) -> str:
    current = now or datetime.now()
    hour = current.hour
    if 5 <= hour < 12:
        return "Good morning, Rushikesh. Mythos is online. Let's make today count."
    if 12 <= hour < 17:
        return "Good afternoon, Rushikesh. Ready when you are."
    if 17 <= hour < 22:
        return "Good evening, Rushikesh. Let's review the day and plan what matters next."
    return "Welcome back, Rushikesh. I'll keep this concise."


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
    interview_sessions = read_table("interview_sessions")
    project_plans = read_table("project_plans")
    knowledge_artifacts = read_table("knowledge_artifacts")
    unified_messages = read_table("unified_chat_messages")
    automations_df = read_table("automations")
    github_repos = read_table("github_repositories")
    github_activity = read_table("github_activity")

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
    backend_readiness = get_backend_readiness()
    dsa_readiness = get_dsa_interview_readiness()
    system_design_readiness = get_system_design_readiness()
    portfolio_summary = get_project_portfolio_summary()
    ai_readiness = int((cohort_progress * 0.6) + (portfolio_summary.get("portfolio_readiness", 0) * 0.4))
    latest_interview_score = 0
    next_mock = backend_readiness.get("next_focus") or system_design_readiness.get("next_focus") or dsa_readiness.get("next_focus")
    if not interview_sessions.empty:
        latest_interview = interview_sessions.sort_values(["date", "id"]).iloc[-1]
        latest_interview_score = int(float(latest_interview.get("score", 0) or 0))
    active_project = pd.Series(dtype=object)
    latest_project_plan = pd.Series(dtype=object)
    if not projects.empty:
        active_projects = projects[~projects["status"].fillna("").isin(["Done"])]
        active_project = (active_projects if not active_projects.empty else projects).sort_values(["progress_percentage", "id"]).iloc[0]
        if not project_plans.empty:
            matching_plans = project_plans[project_plans["project_id"] == int(active_project["id"])]
            if not matching_plans.empty:
                latest_project_plan = matching_plans.sort_values("id").iloc[-1]
    recent_note_titles = ", ".join(read_table("notes").sort_values(["date", "id"]).tail(3)["title"].tolist()) if not read_table("notes").empty else "No notes yet"
    flashcards_created = 0
    revision_questions_created = 0
    if not knowledge_artifacts.empty:
        flashcards_created = int(knowledge_artifacts["artifact_type"].fillna("").str.contains("flashcard", case=False).sum())
        revision_questions_created = int(knowledge_artifacts["artifact_type"].fillna("").str.contains("revision", case=False).sum())
    assistant_unified = unified_messages[unified_messages["role"] == "assistant"] if not unified_messages.empty else pd.DataFrame()
    recent_command_text = "No command center conversations yet."
    if not assistant_unified.empty:
        recent_command_text = " | ".join(assistant_unified.sort_values("id").tail(3)["content"].fillna("").str.slice(0, 80).tolist())
    github_summary = github_weekly_summary(week_start.isoformat(), week_end.isoformat())
    github_trend = pd.DataFrame(github_activity_trend(14))
    observability_summary = observability_dashboard_summary()

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

    st.subheader("Mythos")
    metric_card("Recent Conversations", len(assistant_unified))
    st.caption(recent_command_text)

    st.subheader("Observability")
    o1, o2, o3, o4, o5 = st.columns(5)
    with o1:
        metric_card("Today's Requests", observability_summary.get("today_requests", 0))
    with o2:
        metric_card("Today's Cost", f"${observability_summary.get('today_cost', 0):.4f}")
    with o3:
        metric_card("Most Used Agent", observability_summary.get("most_used_agent", "None"))
    with o4:
        metric_card("Avg Response", f"{observability_summary.get('average_response_time_ms', 0)} ms")
    with o5:
        metric_card("Errors Today", observability_summary.get("error_count", 0))

    st.subheader("Automation")
    notification_rows = latest_notifications(5)
    unread_count = sum(1 for row in notification_rows if not row.get("is_read"))
    latest_briefing = get_latest_daily_briefing()
    if automations_df.empty:
        st.info("No automations configured yet.")
    else:
        upcoming = automations_df[automations_df["enabled"] == 1].sort_values("next_run_at").head(3)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"**Notification Bell ({unread_count})**")
            show_dataframe(pd.DataFrame(notification_rows)[["title", "category", "priority", "created_at"]] if notification_rows else pd.DataFrame(), "No notifications yet.")
        with c2:
            st.write("**Daily Briefing**")
            if latest_briefing:
                st.write(f"**{latest_briefing.get('briefing_date', '')}**")
                st.caption(latest_briefing.get("morning_brief") or latest_briefing.get("evening_brief") or "Briefing saved.")
            else:
                st.info("No briefing yet.")
        with c3:
            st.write("**Upcoming**")
            show_dataframe(upcoming[["name", "next_run_at", "action_type"]], "No upcoming automations.")
        reports = latest_reports(3)
        if reports:
            st.write("**Latest Reports**")
            show_dataframe(pd.DataFrame(reports)[["title", "category", "priority", "created_at"]])

    st.subheader("GitHub Activity")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        metric_card("Commits This Week", github_summary.get("commits", 0))
    with g2:
        metric_card("Active Repo", github_summary.get("active_repo") or "No activity")
    with g3:
        metric_card("Last Pushed Repo", github_summary.get("last_pushed_repo") or "Not synced")
    with g4:
        metric_card("Tracked Repos", len(github_repos))
    if github_activity.empty:
        st.caption("Sync GitHub from the GitHub Integration page to populate coding activity.")
    elif not github_trend.empty:
        trend_chart = github_trend.rename(columns={"activity_day": "Date", "activity_type": "Type", "count": "Count"})
        st.line_chart(trend_chart, x="Date", y="Count", color="Type", use_container_width=True)

    st.subheader("Study Planning")
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
        st.caption("Ask Mythos for today's study plan to show it here.")
    else:
        st.write(f"**Today's AI Plan:** {latest_learning_plan.get('focus_area', '')}")
        st.caption(str(latest_learning_plan.get("recommended_tasks", "")))

    st.subheader("Weekly Review")
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

    st.subheader("Resume & Interview Readiness")
    i1, i2, i3, i4, i5, i6 = st.columns(6)
    with i1:
        metric_card("Backend Readiness", f"{backend_readiness.get('readiness', 0)}%")
    with i2:
        metric_card("AI Engineer Readiness", f"{ai_readiness}%")
    with i3:
        metric_card("DSA Readiness", f"{dsa_readiness.get('readiness', 0)}%")
    with i4:
        metric_card("System Design", f"{system_design_readiness.get('readiness', 0)}%")
    with i5:
        metric_card("Latest Mock Score", latest_interview_score)
    with i6:
        metric_card("Next Mock", next_mock or "Backend fundamentals")

    st.subheader("Project Focus")
    p1, p2, p3, p4, p5 = st.columns(5)
    next_tasks_text = str(latest_project_plan.get("next_tasks", "") if not latest_project_plan.empty else active_project.get("next_task", "") if not active_project.empty else "")
    next_tasks = [line.strip(" -0123456789.") for line in next_tasks_text.splitlines() if line.strip()]
    with p1:
        metric_card("Active Project", active_project.get("project_name", "No project") if not active_project.empty else "No project")
    with p2:
        metric_card("Current Milestone", active_project.get("current_task", "Not set") if not active_project.empty else "Not set")
    with p3:
        metric_card("Next 3 Tasks", "; ".join(next_tasks[:3]) if next_tasks else "Generate plan")
    with p4:
        metric_card("Project Risk", latest_project_plan.get("risks", "Generate plan") if not latest_project_plan.empty else active_project.get("blockers", "None") if not active_project.empty else "No project")
    with p5:
        metric_card("Resume Angle", latest_project_plan.get("resume_angle", "Generate plan") if not latest_project_plan.empty else "Generate plan")

    st.subheader("Notes & Knowledge")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Recent Notes", recent_note_titles)
    with k2:
        metric_card("Revision Questions Due", revision_due_items.get("total_due", 0))
    with k3:
        metric_card("Flashcards Created", flashcards_created)
    with k4:
        metric_card("Weak Knowledge Areas", weak_topics or "None logged")

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


def project_mentor_agent_page() -> None:
    st.title("Project Mentor Agent")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    projects_df = read_table("projects")
    plans_df = read_table("project_plans")
    if projects_df.empty:
        st.info("Add a project in Projects Tracker first, then generate a mentor plan.")
        show_dataframe(plans_df, "No project plans saved yet.")
        return

    project_options = {
        f"{int(row['id'])} - {row['project_name']} ({row['status']})": int(row["id"])
        for _, row in projects_df.sort_values(["status", "progress_percentage", "id"]).iterrows()
    }
    selected_label = st.selectbox("Project", list(project_options.keys()))
    selected_project_id = project_options[selected_label]
    selected_project = projects_df[projects_df["id"] == selected_project_id].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Status", selected_project.get("status", ""))
    with c2:
        metric_card("Progress", f"{int(selected_project.get('progress_percentage', 0) or 0)}%")
    with c3:
        metric_card("Current Task", selected_project.get("current_task", "Not set"))
    with c4:
        metric_card("Next Task", selected_project.get("next_task", "Not set"))

    if st.button("Generate Project Mentor Plan", use_container_width=True):
        prompt = f"Generate a project mentor plan for project_id {selected_project_id}."
        with st.spinner("Calling project mentor tools and generating plan..."):
            response = run_health_agent("project_mentor", prompt)
        st.session_state.project_mentor_last_response = response

    prompt = st.chat_input("Ask for roadmap, next tasks, README, or resume positioning")
    if prompt:
        full_prompt = f"{prompt}\nProject id: {selected_project_id}."
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling project mentor tools..."):
                response = run_health_agent("project_mentor", full_prompt)
            st.write(response)

    last_response = st.session_state.get("project_mentor_last_response", "")
    if last_response:
        st.subheader("Latest Generated Plan")
        st.write(last_response)

    st.subheader("Recent Project Mentor Messages")
    for message in get_recent_chat_messages("project_mentor", 8):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.subheader("Saved Project Plans")
    show_dataframe(plans_df, "No project plans saved yet.")

    with st.expander("Recent project mentor tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("project_mentor", 50))
        show_dataframe(logs, "No project mentor tool logs yet.")


def resume_interview_coach_page() -> None:
    st.title("Resume & Interview Coach Agent")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    sessions_df = read_table("interview_sessions")
    projects_df = read_table("projects")
    backend_ready = get_backend_readiness()
    dsa_ready = get_dsa_interview_readiness()
    system_ready = get_system_design_readiness()
    portfolio = get_project_portfolio_summary()

    ai_progress = 0
    cohort_df = read_table("ai_cohort")
    if not cohort_df.empty:
        ai_progress = int(cohort_df["completion_percentage"].fillna(0).mean())
    ai_ready = int((ai_progress * 0.6) + (portfolio.get("portfolio_readiness", 0) * 0.4))
    latest_score = 0
    if not sessions_df.empty:
        latest_score = int(float(sessions_df.sort_values(["date", "id"]).iloc[-1].get("score", 0) or 0))

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Backend SDE2", f"{backend_ready.get('readiness', 0)}%")
    with c2:
        metric_card("AI Engineer", f"{ai_ready}%")
    with c3:
        metric_card("DSA", f"{dsa_ready.get('readiness', 0)}%")
    with c4:
        metric_card("System Design", f"{system_ready.get('readiness', 0)}%")
    with c5:
        metric_card("Latest Mock", latest_score)

    project_options = {"All projects": 0}
    if not projects_df.empty:
        project_options.update({f"{int(row['id'])} - {row['project_name']}": int(row["id"]) for _, row in projects_df.iterrows()})
    selected_project = st.selectbox("Resume bullet source", list(project_options.keys()))
    selected_project_id = project_options[selected_project]

    topic = st.text_input("Mock interview topic", value=backend_ready.get("next_focus") or "Backend fundamentals")
    user_answers = st.text_area("Paste your mock answers for feedback", height=160)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Assess Readiness", use_container_width=True):
            with st.spinner("Calling interview readiness tools..."):
                response = run_health_agent("resume_interview", "Assess my Backend SDE2 and AI Engineer interview readiness.")
            st.session_state.resume_interview_last_response = response
    with c2:
        if st.button("Generate Resume Bullets", use_container_width=True):
            project_text = f" for project_id {selected_project_id}" if selected_project_id else ""
            with st.spinner("Calling portfolio and resume tools..."):
                response = run_health_agent("resume_interview", f"Generate resume bullets{project_text}.")
            st.session_state.resume_interview_last_response = response
    with c3:
        if st.button("Run Mock Interview", use_container_width=True):
            prompt = f"Generate mock interview questions for topic: {topic}."
            if user_answers.strip():
                prompt += f"\nEvaluate these answers and save the interview session:\n{user_answers}"
            with st.spinner("Calling mock interview tools..."):
                response = run_health_agent("resume_interview", prompt)
            st.session_state.resume_interview_last_response = response

    prompt = st.chat_input("Ask for resume bullets, readiness, questions, or answer feedback")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling resume and interview tools..."):
                response = run_health_agent("resume_interview", prompt)
            st.write(response)

    last_response = st.session_state.get("resume_interview_last_response", "")
    if last_response:
        st.subheader("Latest Coach Response")
        st.write(last_response)

    st.subheader("Recent Resume & Interview Messages")
    for message in get_recent_chat_messages("resume_interview", 8):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.subheader("Saved Interview Sessions")
    show_dataframe(sessions_df, "No interview sessions saved yet.")

    with st.expander("Recent resume/interview tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("resume_interview", 50))
        show_dataframe(logs, "No resume/interview tool logs yet.")


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


def memory_management_page() -> None:
    st.title("Mythos Memory")
    st.caption("Manage what Mythos remembers across study, health, projects, notes, and interview prep.")
    initialize_memory_tables()

    with st.form("add_memory_form", clear_on_submit=True):
        st.subheader("Add Memory")
        c1, c2, c3 = st.columns(3)
        with c1:
            memory_type = st.selectbox("Type", ["goal", "preference", "struggle", "fact", "plan", "other"])
        with c2:
            importance = st.slider("Importance", 1, 5, 3)
        with c3:
            pinned = st.checkbox("Pin")
        content = st.text_area("Memory")
        submitted = st.form_submit_button("Save Memory")
    if submitted:
        result = save_memory(content, memory_type=memory_type, source="manual", importance=importance, pinned=pinned)
        if result.get("saved"):
            st.success("Memory saved.")
        else:
            st.info(result.get("reason", "Memory was not saved."))

    query = st.text_input("Search memories", placeholder="goals, diet preference, weak topic, project plan...")
    if query:
        memories = search_memory(query, top_k=20)
        df = pd.DataFrame(memories)
    else:
        df = pd.DataFrame(get_all_memories())

    if df.empty:
        st.info("No memories yet.")
        return

    st.subheader("Memories")
    show_dataframe(df)

    selected_id = st.selectbox("Select memory to edit", df["id"].astype(int).tolist())
    selected = df[df["id"] == selected_id].iloc[0]
    with st.form("edit_memory_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            edit_type = st.selectbox(
                "Edit type",
                ["goal", "preference", "struggle", "fact", "plan", "other"],
                index=["goal", "preference", "struggle", "fact", "plan", "other"].index(selected.get("memory_type", "fact"))
                if selected.get("memory_type", "fact") in ["goal", "preference", "struggle", "fact", "plan", "other"]
                else 3,
            )
        with c2:
            edit_importance = st.slider("Edit importance", 1, 5, int(selected.get("importance", 3) or 3))
        with c3:
            edit_pinned = st.checkbox("Pinned", value=bool(selected.get("pinned", 0)))
        edit_content = st.text_area("Edit memory", value=selected.get("content", ""))
        c1, c2 = st.columns(2)
        with c1:
            update_submitted = st.form_submit_button("Update Memory")
        with c2:
            delete_submitted = st.form_submit_button("Delete Memory")

    if update_submitted:
        update_memory(
            int(selected_id),
            edit_content,
            edit_type,
            selected.get("source", "manual"),
            edit_importance,
            edit_pinned,
        )
        st.success("Memory updated.")
        st.rerun()
    if delete_submitted:
        delete_memory(int(selected_id))
        st.success("Memory deleted.")
        st.rerun()


def automations_page() -> None:
    st.title("Automations")
    st.caption("Mythos can proactively create reminders, briefs, checks, and reports from your tracker data.")
    initialize_automation_tables()

    automations = list_automations()
    if not automations:
        st.info("No automations configured.")
        return

    automations_df = pd.DataFrame(automations)
    enabled_count = int(automations_df["enabled"].fillna(0).sum())
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Enabled", enabled_count)
    with c2:
        metric_card("Total", len(automations_df))
    with c3:
        next_run = automations_df[automations_df["enabled"] == 1].sort_values("next_run_at").head(1)
        metric_card("Next Run", next_run.iloc[0]["next_run_at"] if not next_run.empty else "None")

    st.subheader("Manage Automations")
    for automation in automations:
        with st.expander(f"{automation['name']} - {automation['action_type']}", expanded=False):
            st.write(automation.get("description", ""))
            st.caption(f"Schedule: {automation.get('schedule_type')} at {automation.get('run_time')} | Next: {automation.get('next_run_at')}")
            enabled = st.toggle(
                "Enabled",
                value=bool(automation.get("enabled", 1)),
                key=f"automation_enabled_{automation['id']}",
            )
            if enabled != bool(automation.get("enabled", 1)):
                update_automation_enabled(int(automation["id"]), enabled)
                st.success("Automation updated.")
                st.rerun()
            if st.button("Run now", key=f"run_automation_{automation['id']}"):
                with st.spinner("Running automation..."):
                    result = run_automation(int(automation["id"]), lambda prompt: execute_command_center_prompt(prompt)[0])
                if result.get("ran"):
                    st.success("Automation completed.")
                    st.write(result.get("output", ""))
                else:
                    st.error(result.get("message") or result.get("reason") or "Automation failed.")

    st.subheader("Execution History")
    logs_df = pd.DataFrame(list_automation_logs(100))
    show_dataframe(logs_df, "No automation runs yet.")


def notifications_page() -> None:
    st.title("Notifications")
    st.caption("Proactive messages and reports generated by Mythos automations.")

    c1, c2, c3 = st.columns(3)
    with c1:
        category = st.selectbox("Category", ["All", "study", "health", "career", "project", "system"])
    with c2:
        priority = st.selectbox("Priority", ["All", "low", "medium", "high"])
    with c3:
        include_read = st.checkbox("Include read", value=True)

    notifications = list_notifications(category, priority, include_read)
    if not notifications:
        st.info("No notifications found.")
    else:
        for notification in notifications:
            read_label = "Read" if notification.get("is_read") else "Unread"
            with st.expander(
                f"{notification.get('title', 'Notification')} - {notification.get('priority', 'medium')} - {read_label}",
                expanded=not bool(notification.get("is_read")),
            ):
                st.caption(f"{notification.get('category', 'system')} | {notification.get('source', '')} | {notification.get('created_at', '')}")
                st.write(notification.get("message", ""))
                if not notification.get("is_read"):
                    if st.button("Mark as read", key=f"mark_read_{notification['id']}"):
                        mark_notification_read(int(notification["id"]), True)
                        st.rerun()

    st.subheader("Daily Briefings")
    briefings_df = read_table("daily_briefings")
    show_dataframe(briefings_df, "No daily briefings yet.")


def observability_center_page() -> None:
    st.title("Observability Center")
    st.caption("Local analytics for Mythos agent, tool, router, LLM, memory, cost, errors, and latency activity.")
    initialize_observability_tables()

    summary = observability_dashboard_summary()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Today's Requests", summary.get("today_requests", 0))
    with c2:
        metric_card("Today's Cost", f"${summary.get('today_cost', 0):.4f}")
    with c3:
        metric_card("Most Used Agent", summary.get("most_used_agent", "None"))
    with c4:
        metric_card("Avg Response", f"{summary.get('average_response_time_ms', 0)} ms")
    with c5:
        metric_card("Errors Today", summary.get("error_count", 0))

    tabs = st.tabs([
        "Overview",
        "Agents",
        "Tools",
        "Router",
        "LLM & Cost",
        "Memory",
        "Errors",
        "Latency",
    ])

    with tabs[0]:
        requests_day = daily_metric("llm_requests", "count")
        tokens_day = daily_metric("llm_requests", "tokens")
        cost_day = daily_metric("llm_requests", "cost")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Requests/day")
            if requests_day.empty:
                st.info("No LLM requests logged yet.")
            else:
                st.line_chart(requests_day, x="day", y="value", use_container_width=True)
        with c2:
            st.subheader("Tokens/day")
            if tokens_day.empty:
                st.info("No token usage logged yet.")
            else:
                st.line_chart(tokens_day, x="day", y="value", use_container_width=True)
        st.subheader("Cost/day")
        if cost_day.empty:
            st.info("No cost data logged yet.")
        else:
            st.line_chart(cost_day, x="day", y="value", use_container_width=True)

    with tabs[1]:
        st.subheader("Agent Analytics")
        agent_usage = top_counts("agent_executions", "agent_name")
        agent_df = read_observability_table("agent_executions")
        if agent_usage.empty:
            st.info("No agent executions logged yet.")
        else:
            st.bar_chart(agent_usage, x="name", y="count", use_container_width=True)
        show_dataframe(agent_df, "No agent executions logged yet.")

    with tabs[2]:
        st.subheader("Tool Analytics")
        tool_usage = top_counts("tool_executions", "tool_name")
        tool_df = read_observability_table("tool_executions")
        if tool_usage.empty:
            st.info("No tool executions logged yet.")
        else:
            st.bar_chart(tool_usage, x="name", y="count", use_container_width=True)
        show_dataframe(tool_df, "No tool executions logged yet.")

    with tabs[3]:
        st.subheader("Router Analytics")
        router_usage = top_counts("router_executions", "selected_agent")
        router_df = read_observability_table("router_executions")
        if router_usage.empty:
            st.info("No router executions logged yet.")
        else:
            st.bar_chart(router_usage, x="name", y="count", use_container_width=True)
        if not router_df.empty:
            confidence_df = router_df.copy()
            confidence_df["created_day"] = pd.to_datetime(confidence_df["created_at"], errors="coerce").dt.date.astype(str)
            confidence_day = confidence_df.groupby("created_day", as_index=False)["confidence"].mean()
            st.line_chart(confidence_day, x="created_day", y="confidence", use_container_width=True)
        show_dataframe(router_df, "No router executions logged yet.")

    with tabs[4]:
        st.subheader("LLM Analytics and Cost Dashboard")
        llm_df = read_observability_table("llm_requests")
        model_usage = top_counts("llm_requests", "model")
        c1, c2 = st.columns(2)
        with c1:
            if model_usage.empty:
                st.info("No model usage logged yet.")
            else:
                st.bar_chart(model_usage, x="name", y="count", use_container_width=True)
        with c2:
            cost_day = daily_metric("llm_requests", "cost")
            if cost_day.empty:
                st.info("No cost data logged yet.")
            else:
                st.line_chart(cost_day, x="day", y="value", use_container_width=True)
        show_dataframe(llm_df, "No LLM requests logged yet.")

    with tabs[5]:
        st.subheader("Memory Analytics")
        memory_df = read_observability_table("memory_retrievals")
        if memory_df.empty:
            st.info("No memory retrievals logged yet.")
        else:
            daily_memory = memory_df.copy()
            daily_memory["created_day"] = pd.to_datetime(daily_memory["created_at"], errors="coerce").dt.date.astype(str)
            found_day = daily_memory.groupby("created_day", as_index=False)["memories_found"].sum()
            latency_day = daily_memory.groupby("created_day", as_index=False)["retrieval_time_ms"].mean()
            c1, c2 = st.columns(2)
            with c1:
                st.line_chart(found_day, x="created_day", y="memories_found", use_container_width=True)
            with c2:
                st.line_chart(latency_day, x="created_day", y="retrieval_time_ms", use_container_width=True)
        show_dataframe(memory_df, "No memory retrievals logged yet.")

    with tabs[6]:
        st.subheader("Error Dashboard")
        agent_errors = daily_metric("agent_executions", "errors")
        tool_errors = daily_metric("tool_executions", "errors")
        c1, c2 = st.columns(2)
        with c1:
            st.write("Agent error trends")
            if agent_errors.empty:
                st.info("No agent errors logged.")
            else:
                st.line_chart(agent_errors, x="day", y="value", use_container_width=True)
        with c2:
            st.write("Tool error trends")
            if tool_errors.empty:
                st.info("No tool errors logged.")
            else:
                st.line_chart(tool_errors, x="day", y="value", use_container_width=True)
        agent_df = read_observability_table("agent_executions")
        tool_df = read_observability_table("tool_executions")
        errors = []
        if not agent_df.empty:
            errors.append(agent_df[agent_df["success"] == 0].assign(source="agent"))
        if not tool_df.empty:
            errors.append(tool_df[tool_df["success"] == 0].assign(source="tool"))
        error_df = pd.concat(errors, ignore_index=True) if errors else pd.DataFrame()
        show_dataframe(error_df, "No execution errors logged.")

    with tabs[7]:
        st.subheader("Latency Dashboard")
        agent_latency = daily_metric("agent_executions", "latency")
        llm_latency = daily_metric("llm_requests", "latency")
        c1, c2 = st.columns(2)
        with c1:
            st.write("Agent latency trends")
            if agent_latency.empty:
                st.info("No agent latency logged yet.")
            else:
                st.line_chart(agent_latency, x="day", y="value", use_container_width=True)
        with c2:
            st.write("LLM latency trends")
            if llm_latency.empty:
                st.info("No LLM latency logged yet.")
            else:
                st.line_chart(llm_latency, x="day", y="value", use_container_width=True)


def github_integration_page() -> None:
    st.title("GitHub Integration")
    st.caption("Track coding activity so Mythos can connect project work with learning plans, reviews, and career readiness.")
    initialize_github_tables()

    if not github_is_configured():
        st.warning("GITHUB_TOKEN not found. Add GITHUB_TOKEN to your environment to sync repositories and activity.")

    username = st.text_input(
        "GitHub username",
        value=st.session_state.get("github_username", ""),
        placeholder="Leave blank to sync the authenticated token user",
    )
    st.session_state.github_username = username.strip()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        sync_clicked = st.button("Sync repositories", use_container_width=True, disabled=not github_is_configured())
    with c2:
        refresh_clicked = st.button("Refresh saved data", use_container_width=True)
    with c3:
        st.caption("Use a GitHub token with repo read access. Public-only tokens can still sync public activity.")

    if sync_clicked:
        with st.spinner("Syncing GitHub repositories, commits, pull requests, and issues..."):
            try:
                result = sync_github_activity(username.strip() or None)
                st.success(f"Synced {result.get('repositories', 0)} repositories and {result.get('activity_items', 0)} activity items.")
                if result.get("errors"):
                    st.warning("Some repositories could not be fully synced.")
                    for error in result["errors"][:5]:
                        st.caption(error)
            except Exception as exc:
                st.error(str(exc))
    if refresh_clicked:
        st.rerun()

    repos = pd.DataFrame(list_saved_repositories())
    activity = pd.DataFrame(list_github_recent_activity(100))
    weekly = github_weekly_summary()
    links = link_github_to_projects()

    st.subheader("Weekly Coding Activity")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Commits", weekly.get("commits", 0))
    with c2:
        metric_card("Pull Requests", weekly.get("pull_requests", 0))
    with c3:
        metric_card("Issues", weekly.get("issues", 0))
    with c4:
        metric_card("Active Repo", weekly.get("active_repo") or "None")
    with c5:
        metric_card("Last Pushed", weekly.get("last_pushed_repo") or "None")

    trend = pd.DataFrame(github_activity_trend(30))
    if not trend.empty:
        trend = trend.rename(columns={"activity_day": "Date", "activity_type": "Type", "count": "Count"})
        st.line_chart(trend, x="Date", y="Count", color="Type", use_container_width=True)

    st.subheader("Repositories")
    if repos.empty:
        st.info("No repositories synced yet.")
    else:
        display_repos = repos[["repo_name", "language", "stars", "forks", "last_pushed_at", "repo_url"]]
        show_dataframe(display_repos, "No repositories synced yet.")

    st.subheader("Recent Commits, PRs, and Issues")
    repo_options = ["All"] + (repos["repo_name"].dropna().tolist() if not repos.empty else [])
    selected_repo = st.selectbox("Repository filter", repo_options)
    filtered_activity = pd.DataFrame(list_github_recent_activity(100, selected_repo))
    if filtered_activity.empty:
        st.info("No GitHub activity synced yet.")
    else:
        show_dataframe(
            filtered_activity[["repo_name", "activity_type", "title", "activity_date", "url"]],
            "No GitHub activity synced yet.",
        )

    st.subheader("Project Links")
    if links:
        show_dataframe(pd.DataFrame(links), "No repository/project links detected.")
    else:
        st.caption("Add GitHub links to projects or use similar project/repo names to help Mythos link activity automatically.")


def notes_knowledge_assistant_page() -> None:
    st.title("Notes & Knowledge Assistant")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")

    notes_df = read_table("notes")
    artifacts_df = read_table("knowledge_artifacts")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Notes", len(notes_df))
    with c2:
        metric_card("Artifacts", len(artifacts_df))
    with c3:
        flashcards = int(artifacts_df["artifact_type"].fillna("").str.contains("flashcard", case=False).sum()) if not artifacts_df.empty else 0
        metric_card("Flashcards", flashcards)
    with c4:
        revisions = int(artifacts_df["artifact_type"].fillna("").str.contains("revision", case=False).sum()) if not artifacts_df.empty else 0
        metric_card("Revision Sets", revisions)

    quick_query = st.text_input("Topic or note search", placeholder="JWT, indexing, system design, DP...")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Search & Summarize", use_container_width=True, disabled=not quick_query.strip()):
            with st.spinner("Searching notes and building summary..."):
                response = run_health_agent("knowledge_assistant", f"Search and summarize notes for: {quick_query}")
            st.session_state.knowledge_last_response = response
    with c2:
        if st.button("Generate Revision Questions", use_container_width=True, disabled=not quick_query.strip()):
            with st.spinner("Generating revision questions..."):
                response = run_health_agent("knowledge_assistant", f"Generate revision questions for: {quick_query}")
            st.session_state.knowledge_last_response = response
    with c3:
        if st.button("Connect Across Tracks", use_container_width=True, disabled=not quick_query.strip()):
            with st.spinner("Connecting related notes..."):
                response = run_health_agent("knowledge_assistant", f"Connect notes and learning tracks related to: {quick_query}")
            st.session_state.knowledge_last_response = response

    prompt = st.chat_input("Ask to search, summarize, create flashcards, or revise a topic")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Calling knowledge tools..."):
                response = run_health_agent("knowledge_assistant", prompt)
            st.write(response)

    last_response = st.session_state.get("knowledge_last_response", "")
    if last_response:
        st.subheader("Latest Knowledge Output")
        st.write(last_response)

    st.subheader("Recent Knowledge Messages")
    for message in get_recent_chat_messages("knowledge_assistant", 8):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.subheader("Knowledge Artifacts")
    show_dataframe(artifacts_df, "No knowledge artifacts saved yet.")

    with st.expander("Recent knowledge assistant tool logs"):
        logs = pd.DataFrame(get_recent_tool_logs("knowledge_assistant", 50))
        show_dataframe(logs, "No knowledge assistant tool logs yet.")


def ai_command_center_page() -> None:
    st.title("Mythos")
    st.caption("Your personal AI command center for study, health, projects, notes, and interview prep.")
    settings = get_voice_settings()

    for message in get_recent_unified_chat(10):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    voice_enabled = st.toggle("Voice Mode", value=st.session_state.get("voice_mode_enabled", False))
    st.session_state.voice_mode_enabled = voice_enabled

    if voice_enabled:
        st.subheader("Voice Mode")
        if not os.getenv("OPENAI_API_KEY"):
            st.error("OpenAI API key not found. Please add OPENAI_API_KEY to your environment.")
        if bool(settings.get("startup_greeting_enabled", 1)):
            greeting = mythos_startup_greeting()
            st.info(greeting)
            if bool(settings.get("autoplay_enabled", 1)) and st.session_state.get("last_voice_greeting") != date.today().isoformat():
                try:
                    greeting_audio = generate_voice_response(greeting, settings)
                    st.audio(greeting_audio, format="audio/mp3", autoplay=True)
                    st.session_state.last_voice_greeting = date.today().isoformat()
                except Exception:
                    pass

        st.caption("Click the microphone, speak naturally, review the transcript, then send it to Mythos.")

        with st.expander("Voice Settings", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                voice_name = st.selectbox(
                    "Voice",
                    ["onyx", "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "sage", "shimmer"],
                    index=["onyx", "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "sage", "shimmer"].index(settings.get("voice_name", "onyx"))
                    if settings.get("voice_name", "onyx") in ["onyx", "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "sage", "shimmer"]
                    else 0,
                )
            with c2:
                stt_model = st.selectbox(
                    "Speech-to-text",
                    ["gpt-4o-mini-transcribe", "whisper-1"],
                    index=0 if settings.get("stt_model", "gpt-4o-mini-transcribe") != "whisper-1" else 1,
                )
            with c3:
                tts_model = st.selectbox(
                    "Text-to-speech",
                    ["gpt-4o-mini-tts", "tts-1"],
                    index=0 if settings.get("tts_model", "gpt-4o-mini-tts") != "tts-1" else 1,
                )
            c1, c2, c3 = st.columns(3)
            with c1:
                speaking_speed = st.slider("Speaking speed", 0.75, 1.25, float(settings.get("speaking_speed", 0.95) or 0.95), 0.05)
            with c2:
                response_style = st.selectbox(
                    "Response style",
                    ["concise", "balanced", "detailed"],
                    index=["concise", "balanced", "detailed"].index(settings.get("response_style", "concise"))
                    if settings.get("response_style", "concise") in ["concise", "balanced", "detailed"]
                    else 0,
                )
            with c3:
                autoplay_enabled = st.checkbox("Autoplay", value=bool(settings.get("autoplay_enabled", 1)))
            c1, c2, c3 = st.columns(3)
            with c1:
                transcript_confirmation_enabled = st.checkbox("Confirm transcript", value=bool(settings.get("transcript_confirmation_enabled", 1)))
            with c2:
                save_audio_history_enabled = st.checkbox("Save audio history", value=bool(settings.get("save_audio_history_enabled", 1)))
            with c3:
                startup_greeting_enabled = st.checkbox("Startup greeting", value=bool(settings.get("startup_greeting_enabled", 1)))
            if st.button("Save Voice Settings", use_container_width=True):
                update_voice_settings(
                    {
                        "voice_name": voice_name,
                        "tts_model": tts_model,
                        "stt_model": stt_model,
                        "speaking_speed": speaking_speed,
                        "response_style": response_style,
                        "autoplay_enabled": autoplay_enabled,
                        "transcript_confirmation_enabled": transcript_confirmation_enabled,
                        "save_audio_history_enabled": save_audio_history_enabled,
                        "startup_greeting_enabled": startup_greeting_enabled,
                    }
                )
                st.success("Voice settings saved.")
                st.rerun()

        def run_voice_request(transcript_text: str) -> None:
            response = ""
            audio_file_path = ""
            voice_context = get_voice_personality_prompt(settings.get("response_style", "concise"))
            with st.chat_message("user"):
                st.write(transcript_text)
            with st.chat_message("assistant"):
                try:
                    with st.spinner("Thinking..."):
                        response, _routing = execute_command_center_prompt(transcript_text, context_prefix=voice_context)
                    st.write(response)
                except Exception as exc:
                    response = "I ran into an issue while processing that. Please try again, or use text input."
                    st.error(f"{response} Details: {exc}")
                try:
                    with st.spinner("Speaking..."):
                        audio_bytes = generate_voice_response(response, settings)
                    if bool(settings.get("save_audio_history_enabled", 1)):
                        audio_file_path = save_audio_response(audio_bytes)
                    st.session_state.voice_response_audio = audio_bytes
                    st.session_state.voice_response_text = response
                    st.audio(audio_bytes, format="audio/mp3", autoplay=bool(settings.get("autoplay_enabled", 1)))
                except Exception as exc:
                    st.info(f"Voice playback is unavailable right now, so I showed the answer as text. Details: {exc}")
            persist_voice_conversation(
                transcript_text,
                response,
                audio_file_path,
                settings.get("stt_model", ""),
                settings.get("tts_model", ""),
                settings.get("voice_name", ""),
            )

        quick_commands = [
            "What should I study today?",
            "Analyze my diet",
            "Analyze my workout",
            "Give me my weekly review",
            "What are my weak areas?",
            "Summarize today",
            "How is my health progress?",
            "What should I focus on next?",
        ]
        st.write("Quick voice commands")
        quick_cols = st.columns(4)
        for index, command in enumerate(quick_commands):
            with quick_cols[index % 4]:
                if st.button(command, key=f"voice_quick_{index}", use_container_width=True):
                    run_voice_request(command)

        audio_value = None
        if hasattr(st, "audio_input"):
            audio_value = st.audio_input("Microphone")
        else:
            st.info("Microphone recording is unavailable in this Streamlit version. Upload a recording or use text chat below.")
            audio_value = st.file_uploader("Upload a voice recording", type=["wav", "mp3", "m4a", "ogg", "webm"])

        if audio_value is not None:
            audio_bytes_for_id = audio_value.getvalue()
            audio_id = f"{getattr(audio_value, 'name', 'recording')}:{len(audio_bytes_for_id)}:{audio_bytes_for_id[:64]!r}"
        else:
            audio_id = ""

        if audio_value is not None and st.session_state.get("last_voice_audio_id") != audio_id:
            st.session_state.last_voice_audio_id = audio_id
            st.session_state.voice_transcript = ""
            st.session_state.voice_response_audio = b""
            st.session_state.voice_response_text = ""
            try:
                with st.status("Transcribing voice input...", expanded=False):
                    st.session_state.voice_transcript = handle_voice_input(audio_value, settings)
            except Exception as exc:
                st.warning(f"Voice transcription failed. You can use text input below. Details: {exc}")

        transcript = st.text_area(
            "Transcript",
            value=st.session_state.get("voice_transcript", ""),
            placeholder="Your transcribed voice message will appear here.",
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            send_label = "Send to Mythos" if bool(settings.get("transcript_confirmation_enabled", 1)) else "Run Voice Command"
            send_voice = st.button(send_label, use_container_width=True, disabled=not transcript.strip())
        with c2:
            clear_voice = st.button("Clear Voice Draft", use_container_width=True)

        if clear_voice:
            st.session_state.voice_transcript = ""
            st.session_state.voice_response_text = ""
            st.session_state.voice_response_audio = b""
            st.rerun()

        if send_voice:
            run_voice_request(transcript)
            st.session_state.voice_transcript = ""

        if st.session_state.get("voice_response_audio"):
            st.audio(st.session_state.voice_response_audio, format="audio/mp3")

    prompt = st.chat_input("Type if voice is unavailable...")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response, _routing = execute_command_center_prompt(prompt)
            st.write(response)
        st.rerun()

    with st.expander("Voice conversation history"):
        show_dataframe(read_table("voice_conversations"), "No voice conversations yet.")


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

    st.subheader("Health Overview")
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        metric_card("Latest Health Score", latest_health_score)
    with h2:
        metric_card("Weekly Workouts", workout_summary.get("workout_count", 0))
    with h3:
        metric_card("Avg Protein", f"{protein_summary.get('avg_protein_g', 0):.0f} g")
    with h4:
        metric_card("Weight Trend", weight_trend.get("trend", "not enough data"))
    st.caption(latest_recommendation or "Ask Mythos for a health report to see the latest recommendation here.")

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
    "AI Command Center": ai_command_center_page,
    "Daily Log": daily_log_page,
    "DSA Tracker": dsa_tracker_page,
    "AI Cohort Tracker": ai_cohort_page,
    "System Design Tracker": system_design_page,
    "System Design Course Tracker": system_design_course_page,
    "Backend Deep Dive": backend_page,
    "Backend Course Tracker": backend_course_page,
    "Projects Tracker": projects_page,
    "Notes / Learnings": notes_page,
    "GitHub Integration": github_integration_page,
    "Mythos Memory": memory_management_page,
    "Automations": automations_page,
    "Notifications": notifications_page,
    "Observability Center": observability_center_page,
    "Weekly Review": weekly_review_page,
    "Export Data": export_page,
    "Health Dashboard": health_dashboard_page,
    "Gym Tracker": gym_tracker_page,
    "Diet Tracker": diet_tracker_page,
    "Weight & Steps Tracker": weight_steps_tracker_page,
}

STUDY_PAGES = [
    "Dashboard",
    "AI Command Center",
    "Daily Log",
    "DSA Tracker",
    "AI Cohort Tracker",
    "System Design Tracker",
    "System Design Course Tracker",
    "Backend Deep Dive",
    "Backend Course Tracker",
    "Projects Tracker",
    "Notes / Learnings",
    "GitHub Integration",
    "Mythos Memory",
    "Automations",
    "Notifications",
    "Observability Center",
    "Weekly Review",
    "Export Data",
]

HEALTH_PAGES = [
    "Health Dashboard",
    "Gym Tracker",
    "Diet Tracker",
    "Weight & Steps Tracker",
]


def set_current_page(page_name: str) -> None:
    st.session_state.current_page = page_name


def configure_openai_key() -> None:
    env_path = Path(".env")
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

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
    scheduler_tick(lambda prompt: execute_command_center_prompt(prompt)[0], limit=2)

    st.sidebar.title(APP_NAME)
    st.sidebar.subheader("Study Timetable & Projects")
    if "current_page" not in st.session_state:
        st.session_state.current_page = "AI Command Center"
    visible_pages = set(STUDY_PAGES + HEALTH_PAGES)
    if st.session_state.current_page not in visible_pages:
        st.session_state.current_page = "AI Command Center"
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
