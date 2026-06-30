from __future__ import annotations

import os
import json
from typing import Literal

from openai import OpenAI

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


def run_health_agent(bot_type: Literal["gym", "diet", "health_manager"], user_input: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "OpenAI API key not found. Please add OPENAI_API_KEY to your environment."

    client = OpenAI()
    if bot_type == "gym":
        tools = GYM_TOOLS
        system_prompt = gym_prompt()
    elif bot_type == "diet":
        tools = DIET_TOOLS
        system_prompt = diet_prompt()
    else:
        tools = HEALTH_MANAGER_TOOLS
        system_prompt = health_manager_prompt()

    save_chat_message(bot_type, "user", user_input)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(get_recent_chat_messages(bot_type, 10))
    last_saved_gym_session_id = None

    for _ in range(8):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            final = message.content or ""
            if bot_type == "gym" and last_saved_gym_session_id:
                update_gym_session_analysis(last_saved_gym_session_id, final)
            save_chat_message(bot_type, "assistant", final)
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
    return final


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
