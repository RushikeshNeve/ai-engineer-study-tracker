from __future__ import annotations

import os
import json
import time
from typing import Literal

from openai import OpenAI

from services.memory_service import retrieve_context
from services.observability_service import log_agent_execution, log_llm_request
from tools import call_tool, get_recent_chat_messages, save_chat_message, update_gym_session_analysis


MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

GYM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fitness_profile",
            "description": "Get Rushikesh's fitness profile and fat-loss goal.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_split",
            "description": "Get the planned weekly gym split.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_gym_sessions",
            "description": "Read recent gym sessions from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_previous_sessions_by_type",
            "description": "Read previous sessions matching a workout type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_type": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["session_type", "limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_workout_text",
            "description": "Parse Lyfta-style workout text into a structured gym session.",
            "parameters": {
                "type": "object",
                "properties": {"raw_text": {"type": "string"}},
                "required": ["raw_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_gym_session",
            "description": "Save a parsed gym session and exercises to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"parsed_workout": {"type": "object"}},
                "required": ["parsed_workout"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_gym_session_analysis",
            "description": "Attach the final coach analysis to a saved gym session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "analysis": {"type": "string"},
                },
                "required": ["session_id", "analysis"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gym_progress_summary",
            "description": "Summarize overall gym progress from SQLite.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_gym_charts_data",
            "description": "Return chart-ready gym progress data.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]

DIET_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fitness_profile",
            "description": "Get Rushikesh's fitness profile, target weight, protein target, calorie target, and diet type.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diet_context",
            "description": "Get common food items, protein add-ons, diet strengths, issues, and recommendations for Rushikesh.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_diet_logs",
            "description": "Read recent diet logs from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diet_logs_by_date",
            "description": "Read diet logs for one date.",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string"}},
                "required": ["date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_diet_log",
            "description": "Save an estimated diet log to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"diet_log": {"type": "object"}},
                "required": ["diet_log"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weight_logs",
            "description": "Read recent weight and steps logs.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_weight_log",
            "description": "Save a weight and steps log.",
            "parameters": {
                "type": "object",
                "properties": {"weight_log": {"type": "object"}},
                "required": ["weight_log"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diet_progress_summary",
            "description": "Summarize diet progress from SQLite.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_diet_macros",
            "description": "Estimate calories and macros from natural language meals.",
            "parameters": {
                "type": "object",
                "properties": {"raw_diet_text": {"type": "string"}},
                "required": ["raw_diet_text"],
                "additionalProperties": False,
            },
        },
    },
]

HEALTH_MANAGER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_gym_sessions",
            "description": "Read recent gym sessions from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_diet_logs",
            "description": "Read recent diet logs from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weight_logs",
            "description": "Read recent weight and steps logs from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weekly_workout_count",
            "description": "Calculate current and previous week workout counts.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weekly_avg_protein",
            "description": "Calculate current and previous week average protein.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weekly_avg_calories",
            "description": "Calculate weekly average calories and deficit.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weekly_avg_steps",
            "description": "Calculate weekly average steps.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weight_trend",
            "description": "Calculate recent weight trend from SQLite logs.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_health_score",
            "description": "Calculate a health score and risk flags from workout, diet, steps, and weight data.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_health_report",
            "description": "Save a generated daily or weekly health report to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"report": {"type": "object"}},
                "required": ["report"],
                "additionalProperties": False,
            },
        },
    },
]

LEARNING_COACH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_today_schedule",
            "description": "Get today's fixed study schedule and default Slot 1 / Slot 2 focus.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_daily_logs",
            "description": "Read recent daily study logs from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dsa_progress_summary",
            "description": "Summarize DSA progress, weak topics, confidence, and revision load.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ai_cohort_summary",
            "description": "Summarize AI cohort completion, weak modules, and next modules.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_design_summary",
            "description": "Summarize system design course progress, weak sections, and next sections.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_backend_course_summary",
            "description": "Summarize backend course progress, weak topics, and next topics.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_progress_summary",
            "description": "Summarize project progress, active projects, blockers, and recommended project focus.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revision_due_items",
            "description": "Read DSA, backend, and system design items whose revision due date is today or overdue.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_learning_plan",
            "description": "Save the generated learning plan to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"plan": {"type": "object"}},
                "required": ["plan"],
                "additionalProperties": False,
            },
        },
    },
]

WEEKLY_REVIEW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_week_study_summary",
            "description": "Summarize daily logs, notes, learning plans, slot completion, blockers, and reflections for a week.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_dsa_summary",
            "description": "Summarize DSA problems, topics, confidence, mistakes, and weak topics for a week.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_ai_cohort_summary",
            "description": "Summarize AI cohort progress and weak modules.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_system_design_summary",
            "description": "Summarize weekly and overall system design course progress.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_backend_summary",
            "description": "Summarize weekly and overall backend course progress.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_project_summary",
            "description": "Summarize project progress and blockers.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_github_summary",
            "description": "Summarize weekly GitHub commits, pull requests, issues, active repo, and recent activity.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_health_summary",
            "description": "Summarize gym, diet, weight, steps, and health metrics for a week.",
            "parameters": {
                "type": "object",
                "properties": {"week_start": {"type": "string"}, "week_end": {"type": "string"}},
                "required": ["week_start", "week_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_previous_week_review",
            "description": "Read the latest saved weekly AI review.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weekly_consistency_score",
            "description": "Calculate weekly consistency score from study and health logs.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_burnout_risk",
            "description": "Calculate burnout risk from study load, workout load, calories, protein, and blockers.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_weekly_review",
            "description": "Save the generated weekly AI review to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"review": {"type": "object"}},
                "required": ["review"],
                "additionalProperties": False,
            },
        },
    },
]

PROJECT_MENTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_all_projects",
            "description": "Read all projects from SQLite.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_details",
            "description": "Read one project's details by id.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_notes",
            "description": "Read notes related to a project.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_project_progress",
            "description": "Read recent project progress rows.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_related_learning_topics",
            "description": "Read backend, system design, and AI cohort topics related to a project.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_github_activity",
            "description": "Read recent synced GitHub commits, pull requests, and issues from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_project_links",
            "description": "Read detected links between GitHub repositories and projects.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_project_roadmap",
            "description": "Generate a deterministic roadmap scaffold for a project from SQLite details.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_next_tasks",
            "description": "Generate next implementation tasks for a project from SQLite details.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_project_readme",
            "description": "Generate a README improvement outline for a project.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_project_plan",
            "description": "Save a generated project mentor plan to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"plan": {"type": "object"}},
                "required": ["plan"],
                "additionalProperties": False,
            },
        },
    },
]

KNOWLEDGE_ASSISTANT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search notes by title, content, tags, category, or linked track.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notes_by_category",
            "description": "Read notes in one category.",
            "parameters": {
                "type": "object",
                "properties": {"category": {"type": "string"}},
                "required": ["category"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_notes",
            "description": "Read recent notes.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_linked_notes",
            "description": "Read notes linked to a track.",
            "parameters": {
                "type": "object",
                "properties": {"track": {"type": "string"}},
                "required": ["track"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a new note to SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"note": {"type": "object"}},
                "required": ["note"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_note",
            "description": "Summarize one note by id.",
            "parameters": {
                "type": "object",
                "properties": {"note_id": {"type": "integer"}},
                "required": ["note_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_flashcards",
            "description": "Generate flashcards from one note.",
            "parameters": {
                "type": "object",
                "properties": {"note_id": {"type": "integer"}},
                "required": ["note_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_revision_questions",
            "description": "Generate revision questions for a topic and link related notes.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_knowledge_artifact",
            "description": "Save a generated summary, flashcard set, revision question set, or connected-notes artifact.",
            "parameters": {
                "type": "object",
                "properties": {"artifact": {"type": "object"}},
                "required": ["artifact"],
                "additionalProperties": False,
            },
        },
    },
]

RESUME_INTERVIEW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_project_portfolio_summary",
            "description": "Summarize projects as an interview portfolio and readiness signal.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dsa_interview_readiness",
            "description": "Calculate DSA interview readiness from solved problems, confidence, and weak topics.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_design_readiness",
            "description": "Calculate system design interview readiness.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_backend_readiness",
            "description": "Calculate backend interview readiness.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ai_cohort_summary",
            "description": "Summarize AI cohort completion and weak modules.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_weekly_reviews",
            "description": "Read recent weekly AI reviews.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_repositories_summary",
            "description": "Read synced GitHub repositories, language mix, and latest pushed repository.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_github_activity",
            "description": "Read recent synced GitHub commits, pull requests, and issues from SQLite.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_resume_bullets",
            "description": "Generate resume bullet drafts from project data.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_interview_questions",
            "description": "Generate mock interview questions for a topic.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_interview_session",
            "description": "Save a mock interview session with questions, answers, feedback, and score.",
            "parameters": {
                "type": "object",
                "properties": {"session": {"type": "object"}},
                "required": ["session"],
                "additionalProperties": False,
            },
        },
    },
]

def run_health_agent(
    bot_type: Literal[
        "gym",
        "diet",
        "health_manager",
        "learning_coach",
        "weekly_review",
        "project_mentor",
        "knowledge_assistant",
        "resume_interview",
    ],
    user_input: str,
) -> str:
    agent_started = time.perf_counter()
    if not os.getenv("OPENAI_API_KEY"):
        message = "OpenAI API key not found. Please add OPENAI_API_KEY to your environment."
        log_agent_execution(bot_type, user_input, int((time.perf_counter() - agent_started) * 1000), False, message)
        return message

    client = OpenAI()
    if bot_type == "gym":
        tools = GYM_TOOLS
        system_prompt = gym_prompt()
    elif bot_type == "diet":
        tools = DIET_TOOLS
        system_prompt = diet_prompt()
    elif bot_type == "health_manager":
        tools = HEALTH_MANAGER_TOOLS
        system_prompt = health_manager_prompt()
    elif bot_type == "learning_coach":
        tools = LEARNING_COACH_TOOLS
        system_prompt = learning_coach_prompt()
    elif bot_type == "weekly_review":
        tools = WEEKLY_REVIEW_TOOLS
        system_prompt = weekly_review_prompt()
    elif bot_type == "project_mentor":
        tools = PROJECT_MENTOR_TOOLS
        system_prompt = project_mentor_prompt()
    elif bot_type == "knowledge_assistant":
        tools = KNOWLEDGE_ASSISTANT_TOOLS
        system_prompt = knowledge_assistant_prompt()
    else:
        tools = RESUME_INTERVIEW_TOOLS
        system_prompt = resume_interview_prompt()

    memory_context = retrieve_context(user_input, top_k=5)
    if memory_context:
        system_prompt = f"{system_prompt}\n\n{memory_context}\nUse this memory only when relevant. Do not mention memory retrieval unless asked."

    save_chat_message(bot_type, "user", user_input)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(get_recent_chat_messages(bot_type, 10))
    last_saved_gym_session_id = None

    try:
        for _ in range(10):
            llm_started = time.perf_counter()
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            llm_elapsed_ms = int((time.perf_counter() - llm_started) * 1000)
            usage = getattr(response, "usage", None)
            if usage:
                log_llm_request(
                    response.model or MODEL,
                    getattr(usage, "prompt_tokens", 0) or 0,
                    getattr(usage, "completion_tokens", 0) or 0,
                    getattr(usage, "total_tokens", 0) or 0,
                    llm_elapsed_ms,
                )
            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                final = message.content or ""
                if bot_type == "gym" and last_saved_gym_session_id:
                    update_gym_session_analysis(last_saved_gym_session_id, final)
                save_chat_message(bot_type, "assistant", final)
                log_agent_execution(bot_type, user_input, int((time.perf_counter() - agent_started) * 1000), True)
                return final

            for tool_call in message.tool_calls:
                result = call_tool(tool_call.function.name, tool_call.function.arguments, bot_type)
                if bot_type == "gym" and tool_call.function.name == "save_gym_session":
                    try:
                        parsed_result = json.loads(result)
                        if parsed_result.get("saved") and parsed_result.get("session_id"):
                            last_saved_gym_session_id = int(parsed_result["session_id"])
                    except (TypeError, ValueError):
                        pass
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": result,
                    }
                )

        final = "I used the available tools, but the tool-calling loop reached its limit before a final answer."
        save_chat_message(bot_type, "assistant", final)
        log_agent_execution(bot_type, user_input, int((time.perf_counter() - agent_started) * 1000), False, "tool loop limit reached")
        return final
    except Exception as exc:
        log_agent_execution(bot_type, user_input, int((time.perf_counter() - agent_started) * 1000), False, str(exc))
        raise


def gym_prompt() -> str:
    return """
You are Rushikesh's Gym Coach Bot. You must use tools before giving workout feedback.

When the user pastes Lyfta workout text:
1. Call parse_workout_text(raw_text).
2. Call get_weekly_split().
3. Call get_recent_gym_sessions(limit=6).
4. Call get_previous_sessions_by_type(session_type from parsed workout, limit=3).
5. Compare split match, duration, total volume, set count, exercise count, cardio, and steps.
6. Call save_gym_session(parsed_workout).
7. Give a high-quality coach report using this structure:
   - Saved log: session id if available, date, split, duration, volume, sets.
   - Split check: expected split for that day vs actual split.
   - Volume and density: compare kg, sets, and minutes vs recent and same-type sessions.
   - Progressive overload: identify what improved, stayed flat, or regressed.
   - Exercise quality: mention parsed exercises, weak coverage, missing movement pattern if visible.
   - Cardio and steps: compare conditioning work and steps if present.
   - Recovery risk: fatigue warning based on duration, volume, recent training frequency, and next split.
   - Next workout: 3 concrete targets for next session.

Be specific with numbers from tool results. If a metric was not parsed, say "not captured" instead of inventing it.
Keep it direct, coaching-oriented, and useful for the next workout.

Do not claim a workout was saved unless save_gym_session returned saved=true.
"""


def diet_prompt() -> str:
    return """
You are Rushikesh's Diet Coach Bot for fat loss with muscle retention.
You must use tools before giving diet feedback.

When the user enters meals:
1. Call get_fitness_profile().
2. Call get_diet_context().
3. Call estimate_diet_macros(raw_diet_text).
4. Call get_recent_diet_logs(limit=7).
5. Call get_weight_logs(limit=14).
6. Check protein target 130-150g/day and calories:
   training days 2200-2400, rest days 1900-2200.
7. Call save_diet_log(diet_log).
8. Return a high-quality diet coach report using this structure:
   - Saved log: confirm saved id if available, date, estimated calories and macros.
   - Calorie deficit: report estimated deficit calories and judge whether it is reasonable.
   - Protein target: compare protein against 130-150g/day.
   - Calories: compare against training/rest-day target and warn if too low on training day.
   - Fat-loss suitability: calories, protein, meal timing, and satiety quality.
   - Meal quality: strongest meal and weakest meal based on the entered text.
   - Protein add-ons: suggest practical family-food-friendly add-ons like whey, soya, eggs, paneer, matki, dal, curd/lassi.
   - Trend check: compare with recent diet logs and weight logs if available.
   - Tomorrow improvements: 3 concrete changes, including a protein fix.

Be specific with numbers from tool results. If a value is estimated, label it as estimated.

Do not claim a diet log was saved unless save_diet_log returned saved=true.
"""


def health_manager_prompt() -> str:
    return """
You are Rushikesh's Health Manager Agent for fat loss with muscle retention.
You must use tools before giving a report. Do not generate a report from memory only.

For every daily or weekly report request:
1. Call get_recent_gym_sessions(limit=14).
2. Call get_recent_diet_logs(limit=14).
3. Call get_weight_logs(limit=14).
4. Call calculate_weekly_workout_count().
5. Call calculate_weekly_avg_protein().
6. Call calculate_weekly_avg_calories().
7. Call calculate_weekly_avg_steps().
8. Call calculate_weight_trend().
9. Call calculate_health_score().
10. Call save_health_report(report) with report_type daily or weekly.

The saved report object must include:
- date
- report_type
- health_score
- workout_summary
- diet_summary
- weight_summary
- recovery_summary
- recommendations

Report requirements:
- Compare current week with previous logs when tool data is available.
- Highlight risks: low protein, too-low calories, poor recovery, missed steps, excessive volume, or rising weight.
- Give practical recommendations for fat loss with muscle retention.
- Use specific numbers from tool results.
- If data is missing, say what needs to be logged next.

Final answer structure:
- Saved report: report id if available, type, health score.
- Weekly snapshot: workouts, protein, calories, deficit, steps, weight trend.
- Risks.
- Recommendations for the next 24-48 hours.
- What to log next.

Do not claim a health report was saved unless save_health_report returned saved=true.
"""


def learning_coach_prompt() -> str:
    return """
You are Rushikesh's Learning Coach Agent for his Backend + AI Engineer transition.
You must use tools before giving a study plan. Do not generate a plan from memory only.

For every plan request:
1. Call get_today_schedule().
2. Call get_recent_daily_logs(limit=7).
3. Call get_dsa_progress_summary().
4. Call get_ai_cohort_summary().
5. Call get_system_design_summary().
6. Call get_backend_course_summary().
7. Call get_project_progress_summary().
8. Call get_revision_due_items().
9. Call save_learning_plan(plan).

The saved plan object must include:
- date
- plan_type
- focus_area
- recommended_tasks
- reasoning
- estimated_minutes
- priority

Planning rules:
- Respect Slot 1: 9:30 AM - 12:30 PM, deep work, about 180 minutes.
- Respect Slot 2: 11:00 PM - 12:15 AM, light work, about 75 minutes.
- Keep Slot 2 lighter: revision, notes, planning, or one easy DSA problem.
- Balance AI Cohort, DSA, System Design, Backend, and Projects across the week.
- Prioritize revision due items and weak areas, but do not overload the day.
- Recommend a concrete Slot 1 plan and Slot 2 plan with time boxes.
- Include project focus when an active project needs progress.

Final answer structure:
- Saved plan: plan id if available.
- Slot 1: time-boxed tasks.
- Slot 2: lighter time-boxed tasks.
- Weak areas detected.
- Revision due.
- Project focus.
- Why this plan.

Do not claim a plan was saved unless save_learning_plan returned saved=true.
"""


def weekly_review_prompt() -> str:
    return """
You are Rushikesh's Weekly Review Agent for his Backend + AI Engineer transition and health routine.
You must use tools before giving a weekly review. Do not generate the review from memory only.

For every weekly review request:
1. Identify week_start and week_end from the user request. If not provided, use the current week Monday-Sunday.
2. Call get_week_study_summary(week_start, week_end).
3. Call get_week_dsa_summary(week_start, week_end).
4. Call get_week_ai_cohort_summary(week_start, week_end).
5. Call get_week_system_design_summary(week_start, week_end).
6. Call get_week_backend_summary(week_start, week_end).
7. Call get_week_project_summary(week_start, week_end).
8. Call get_week_github_summary(week_start, week_end).
9. Call get_week_health_summary(week_start, week_end).
10. Call get_previous_week_review().
11. Call calculate_weekly_consistency_score().
12. Call calculate_burnout_risk().
13. Call save_weekly_review(review).

The saved review object must include:
- week_start
- week_end
- study_score
- health_score
- consistency_score
- burnout_risk
- wins
- misses
- weak_areas
- next_week_focus
- recommendations

Review requirements:
- Generate a full weekly review.
- Compare current week with previous week or previous saved review when available.
- Identify wins and missed targets.
- Detect burnout risk.
- Recommend next week's focus.
- Balance study, coding/project activity, gym, diet, sleep, and office workload.
- Use specific numbers from tool results.
- If logs are sparse, say what was missing and avoid pretending precision.

Final answer structure:
- Saved review: review id if available.
- Scores: study, health, consistency, burnout risk.
- Biggest wins.
- Biggest misses.
- Weak areas.
- Health and recovery notes.
- GitHub/project momentum.
- Next week focus.
- Practical recommendations.

Do not claim a weekly review was saved unless save_weekly_review returned saved=true.
"""


def project_mentor_prompt() -> str:
    return """
You are Rushikesh's Project Mentor Agent for backend, AI, and portfolio projects.
You must use tools before giving project advice. Do not generate the plan from memory only.

For every project mentor request:
1. Call get_all_projects().
2. Pick the project_id from the user's request. If no project is specified, choose the most active non-Done project from get_all_projects().
3. Call get_project_details(project_id).
4. Call get_project_notes(project_id).
5. Call get_recent_project_progress(limit=5).
6. Call get_related_learning_topics(project_id).
7. Call get_recent_github_activity(limit=20).
8. Call get_github_project_links().
9. Call generate_project_roadmap(project_id).
10. Call generate_next_tasks(project_id).
11. Call generate_project_readme(project_id).
12. Call save_project_plan(plan).

The saved plan object must include:
- project_id
- plan_type
- roadmap
- next_tasks
- architecture_notes
- risks
- resume_angle

Mentor requirements:
- Generate a practical project roadmap.
- Suggest next implementation tasks.
- Identify missing portfolio features.
- Suggest README improvements.
- Link project work with backend, system design, and AI cohort learning.
- Use synced GitHub commits, PRs, and issues to judge actual coding momentum when available.
- Explain how to position the project on a resume.
- Use concrete project data from tools.
- If no projects exist, tell the user to create a project first and do not claim a plan was saved.

Final answer structure:
- Saved plan: plan id if available.
- Project and current milestone.
- Roadmap.
- Next 3 tasks.
- Architecture notes.
- Missing portfolio features and risks.
- README improvements.
- Related learning topics.
- GitHub activity signals.
- Resume angle.

Do not claim a project plan was saved unless save_project_plan returned saved=true.
"""


def knowledge_assistant_prompt() -> str:
    return """
You are Rushikesh's Notes & Knowledge Assistant for interview revision and connected learning.
You must use tools before answering. Do not answer from memory only.

For search or knowledge review requests:
1. Call search_notes(query) or get_recent_notes(limit=10).
2. Call get_linked_notes(track) or get_notes_by_category(category) when the user mentions a track/category.
3. If a specific note_id is available, call summarize_note(note_id).
4. For flashcards, call generate_flashcards(note_id).
5. For topic revision, call generate_revision_questions(topic).
6. Save useful generated output with save_knowledge_artifact(artifact).

The saved artifact object must include:
- artifact_type
- source_type
- source_id
- title
- content
- tags

Assistant requirements:
- Search and summarize notes.
- Generate flashcards.
- Generate revision questions.
- Connect related notes across DSA, backend, system design, AI cohort, and projects.
- Help revise topics before interviews.
- If no notes are found, suggest exactly what note to add next.
- Use note ids and titles from tool results when possible.

Final answer structure:
- What I found.
- Summary or revision output.
- Cross-links across tracks.
- Interview revision focus.
- Saved artifact id if available.

Do not claim an artifact was saved unless save_knowledge_artifact returned saved=true.
"""


def resume_interview_prompt() -> str:
    return """
You are Rushikesh's Resume & Interview Coach Agent.
You convert tracked progress into interview readiness for Backend SDE2 and AI Engineer roles.
You must use tools before giving readiness, resume, or mock-interview feedback.

For readiness or resume requests:
1. Call get_project_portfolio_summary().
2. Call get_dsa_interview_readiness().
3. Call get_system_design_readiness().
4. Call get_backend_readiness().
5. Call get_ai_cohort_summary().
6. Call get_recent_weekly_reviews(limit=4).
7. Call get_github_repositories_summary().
8. Call get_recent_github_activity(limit=20).
9. Call generate_resume_bullets(project_id) when resume bullets are requested, or project_id can be omitted.

For mock interview requests:
1. Call the readiness tools above.
2. Call generate_interview_questions(topic).
3. If the user provided answers, evaluate them and call save_interview_session(session).
4. If the user only requested questions, save a session with questions and empty user_answers.

The saved session object must include:
- date
- interview_type
- topic
- questions
- user_answers
- feedback
- score

Assessment requirements:
- Assess Backend SDE2 readiness using backend, system design, DSA, and project portfolio evidence.
- Assess AI Engineer readiness using AI cohort progress, AI-related projects, notes, and weekly reviews.
- Use synced GitHub activity as proof of project consistency and portfolio freshness.
- Give a numeric readiness summary when possible.
- Recommend weak areas to improve.
- Generate resume bullets that are honest and based on tracked project data.
- Generate practical mock interview questions.
- Give feedback on answers with a score from 0-100 when answers are present.

Final answer structure:
- Readiness snapshot.
- Resume bullets or mock questions, depending on the request.
- Feedback and score if answers were provided.
- Weak areas.
- Next recommended mock interview.
- Saved session id if save_interview_session returned saved=true.

Do not claim an interview session was saved unless save_interview_session returned saved=true.
"""
