from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


DB_PATH = Path("study_tracker.db")

WEEKLY_SPLIT = {
    "Monday": "Push",
    "Tuesday": "Pull",
    "Wednesday": "Rest + 10k Steps",
    "Thursday": "Legs",
    "Friday": "Upper + Abs",
    "Saturday": "Cardio + Abs",
    "Sunday": "Arms + Shoulders + Forearms",
}

PROFILE_SEED = {
    "name": "Rushikesh",
    "age": 24,
    "height_cm": 173,
    "starting_weight_kg": 96.8,
    "goal_weight_kg": 85,
    "goal": "fat loss with muscle retention and conditioning",
    "diet_type": "eggetarian with occasional non-veg outside",
    "target_protein_range": "130-150",
    "target_calories": "2200-2400 training days, 1900-2200 rest days",
    "water_target_liters": 4,
    "notes": (
        "Lives with family, so diet depends on home-cooked meals. Protein add-ons "
        "are used instead of separate cooking. During Adhik Maas, non-veg at home "
        "is limited. Uses whey, soya chunks, eggs, paneer, matki, dal, curd and "
        "lassi as protein sources."
    ),
}

COMMON_FOOD_ITEMS = {
    "regular oatmeal bowl": {"calories": 500, "protein_g": 40, "carbs_g": 65, "fat_g": 8},
    "oatmeal bowl": {"calories": 500, "protein_g": 40, "carbs_g": 65, "fat_g": 8},
    "1 scoop whey": {"calories": 120, "protein_g": 24, "carbs_g": 3, "fat_g": 2},
    "whey": {"calories": 120, "protein_g": 24, "carbs_g": 3, "fat_g": 2},
    "50g dry soya chunks": {"calories": 170, "protein_g": 26, "carbs_g": 18, "fat_g": 1},
    "70g dry soya chunks": {"calories": 240, "protein_g": 36, "carbs_g": 25, "fat_g": 1},
    "soya chunks": {"calories": 170, "protein_g": 26, "carbs_g": 18, "fat_g": 1},
    "100g paneer": {"calories": 260, "protein_g": 18, "carbs_g": 4, "fat_g": 20},
    "paneer": {"calories": 260, "protein_g": 18, "carbs_g": 4, "fat_g": 20},
    "2 whole eggs": {"calories": 140, "protein_g": 12, "carbs_g": 1, "fat_g": 10},
    "2 eggs": {"calories": 140, "protein_g": 12, "carbs_g": 1, "fat_g": 10},
    "egg": {"calories": 70, "protein_g": 6, "carbs_g": 0, "fat_g": 5},
    "80g raw matki cooked": {"calories": 280, "protein_g": 18, "carbs_g": 45, "fat_g": 2},
    "matki": {"calories": 280, "protein_g": 18, "carbs_g": 45, "fat_g": 2},
    "curd": {"calories": 90, "protein_g": 8, "carbs_g": 8, "fat_g": 3},
    "dahi": {"calories": 90, "protein_g": 8, "carbs_g": 8, "fat_g": 3},
    "protein lassi": {"calories": 180, "protein_g": 20, "carbs_g": 18, "fat_g": 3},
    "whey lassi": {"calories": 180, "protein_g": 24, "carbs_g": 15, "fat_g": 2},
    "chicken": {"calories": 250, "protein_g": 35, "carbs_g": 0, "fat_g": 10},
    "dal": {"calories": 180, "protein_g": 10, "carbs_g": 28, "fat_g": 4},
}

SEED_DIET_RECORDS = [
    ("2026-06-03", "training_day_push", 1965, 116, 900, "Good calorie deficit. Protein was slightly low. Soya addition at lunch was a good choice."),
    ("2026-06-04", "training_day_pull", 2120, 149, 850, "Excellent office dinner choices. Protein target achieved. No dessert and no fried starters."),
    ("2026-06-05", "recovery_day", 1720, 124, 900, "Good recovery day. Calories controlled. Protein decent but slightly below ideal target."),
    ("2026-06-07", "training_day_upper", 2200, 111, 700, "Calories were still controlled. Protein was lower than target. Dinner lacked protein."),
    ("2026-06-09", "training_day_push", 1660, 125, 1200, "Protein improved due to soya. Calories were too low for a training day. Lunch protein was low."),
    ("2026-06-10", "training_day_pull", 2170, 119, 800, "80g raw matki improved protein. Still below 140g target. Adding 50g soya would complete target."),
    ("2026-06-17", "recovery_day", 1625, 92, 900, "Good recovery day and step count. Protein was low. Needed one more whey or soya serving."),
]

DIET_ANALYSIS_SUMMARY = {
    "average_estimated_protein_g": "115-125",
    "target_protein_g": "130-150",
    "average_estimated_calories": "1800-2200",
    "main_strengths": [
        "Regular whey intake",
        "Oatmeal breakfast habit is strong",
        "Soya chunks are being used effectively",
        "Calories generally stay in deficit",
        "Good tracking consistency",
    ],
    "main_issues": [
        "Protein is inconsistent",
        "Dinner often lacks protein",
        "Lunch depends heavily on family food and can be low protein",
        "Some training days have calories too low",
        "Need more planned protein add-ons",
    ],
    "recommendations_for_llm_coach": [
        "Ensure at least 2 strong protein add-ons daily.",
        "Prioritize soya, whey, paneer, eggs, matki and dal during vegetarian periods.",
        "Avoid pushing calories below 1800 on heavy training days.",
        "Recommend a protein add-on whenever lunch or dinner is carb-heavy.",
        "Weekly target should be 900g+ protein across 7 days.",
    ],
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_health_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fitness_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                age INTEGER,
                height_cm REAL,
                starting_weight_kg REAL,
                goal_weight_kg REAL,
                goal TEXT,
                diet_type TEXT,
                target_protein_range TEXT,
                target_calories TEXT,
                water_target_liters REAL,
                notes TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS gym_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT,
                day TEXT,
                session_type TEXT,
                title TEXT,
                duration_minutes INTEGER DEFAULT 0,
                total_volume_kg REAL DEFAULT 0,
                exercise_count INTEGER DEFAULT 0,
                set_count INTEGER DEFAULT 0,
                cardio_minutes INTEGER DEFAULT 0,
                cardio_distance_km REAL DEFAULT 0,
                steps INTEGER DEFAULT 0,
                raw_text TEXT,
                analysis TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS gym_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                exercise_name TEXT,
                set_number INTEGER,
                weight_kg REAL,
                reps INTEGER,
                distance_km REAL,
                time_minutes REAL,
                side_note TEXT,
                FOREIGN KEY(session_id) REFERENCES gym_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS diet_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date TEXT,
                raw_text TEXT,
                calories INTEGER DEFAULT 0,
                protein_g REAL DEFAULT 0,
                carbs_g REAL DEFAULT 0,
                fat_g REAL DEFAULT 0,
                estimated_deficit_calories INTEGER DEFAULT 0,
                meal_quality TEXT,
                notes TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS weight_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date TEXT,
                weight_kg REAL,
                steps INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chatbot_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_type TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chatbot_tool_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_type TEXT,
                tool_name TEXT,
                arguments TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS health_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                report_type TEXT,
                health_score REAL DEFAULT 0,
                workout_summary TEXT,
                diet_summary TEXT,
                weight_summary TEXT,
                recovery_summary TEXT,
                recommendations TEXT,
                created_at TEXT
            );
            """
        )
        ensure_fitness_profile_columns(conn)
        ensure_diet_log_columns(conn)
        seed_fitness_profile(conn)
        seed_gym_history(conn)
        seed_diet_history(conn)


def ensure_fitness_profile_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(fitness_profile)").fetchall()}
    migrations = {
        "diet_type": "ALTER TABLE fitness_profile ADD COLUMN diet_type TEXT",
        "target_protein_range": "ALTER TABLE fitness_profile ADD COLUMN target_protein_range TEXT",
        "target_calories": "ALTER TABLE fitness_profile ADD COLUMN target_calories TEXT",
        "water_target_liters": "ALTER TABLE fitness_profile ADD COLUMN water_target_liters REAL",
        "notes": "ALTER TABLE fitness_profile ADD COLUMN notes TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            conn.execute(sql)


def ensure_diet_log_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(diet_logs)").fetchall()}
    if "estimated_deficit_calories" not in columns:
        conn.execute("ALTER TABLE diet_logs ADD COLUMN estimated_deficit_calories INTEGER DEFAULT 0")
    backfill_diet_deficits(conn)


def backfill_diet_deficits(conn: sqlite3.Connection) -> None:
    seed_deficits = {log_date: deficit for log_date, _, _, _, deficit, _ in SEED_DIET_RECORDS}
    for log_date, deficit in seed_deficits.items():
        conn.execute(
            """
            UPDATE diet_logs
            SET estimated_deficit_calories = ?
            WHERE log_date = ?
              AND (estimated_deficit_calories IS NULL OR estimated_deficit_calories = 0)
            """,
            (deficit, log_date),
        )


def seed_fitness_profile(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM fitness_profile").fetchone()[0]
    if existing:
        conn.execute(
            """
            UPDATE fitness_profile
            SET diet_type = COALESCE(NULLIF(diet_type, ''), ?),
                target_protein_range = COALESCE(NULLIF(target_protein_range, ''), ?),
                target_calories = COALESCE(NULLIF(target_calories, ''), ?),
                water_target_liters = COALESCE(water_target_liters, ?),
                notes = COALESCE(NULLIF(notes, ''), ?)
            WHERE id = (SELECT id FROM fitness_profile ORDER BY id DESC LIMIT 1)
            """,
            (
                PROFILE_SEED["diet_type"],
                PROFILE_SEED["target_protein_range"],
                PROFILE_SEED["target_calories"],
                PROFILE_SEED["water_target_liters"],
                PROFILE_SEED["notes"],
            ),
        )
        return
    conn.execute(
        """
        INSERT INTO fitness_profile (
            name, age, height_cm, starting_weight_kg, goal_weight_kg, goal,
            diet_type, target_protein_range, target_calories, water_target_liters,
            notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            PROFILE_SEED["name"],
            PROFILE_SEED["age"],
            PROFILE_SEED["height_cm"],
            PROFILE_SEED["starting_weight_kg"],
            PROFILE_SEED["goal_weight_kg"],
            PROFILE_SEED["goal"],
            PROFILE_SEED["diet_type"],
            PROFILE_SEED["target_protein_range"],
            PROFILE_SEED["target_calories"],
            PROFILE_SEED["water_target_liters"],
            PROFILE_SEED["notes"],
            datetime.now().isoformat(),
        ),
    )


def seed_gym_history(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM gym_sessions").fetchone()[0]
    if existing:
        return

    rows = [
        ("2026-06-16", "Pull", 71, 6920, 23, 0),
        ("2026-06-18", "Upper Body + Abs", 105, 8550, 31, 0),
        ("2026-06-19", "Lower Body + Abs", 108, 7145, 20, 11720),
        ("2026-06-20", "Cardio + Abs", 40, 1265, 12, 0),
        ("2026-06-21", "Arms + Shoulders + Forearms", 42, 2445, 23, 0),
        ("2026-06-23", "Push", 36, 4505, 23, 0),
    ]
    for session_date, session_type, duration, volume, sets, steps in rows:
        dt = pd.to_datetime(session_date).date()
        conn.execute(
            """
            INSERT INTO gym_sessions (
                session_date, day, session_type, title, duration_minutes,
                total_volume_kg, exercise_count, set_count, cardio_minutes,
                cardio_distance_km, steps, raw_text, analysis, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, 0, ?, ?, ?, ?)
            """,
            (
                session_date,
                dt.strftime("%A"),
                session_type,
                session_type,
                duration,
                volume,
                sets,
                steps,
                "Seeded history",
                "",
                datetime.now().isoformat(),
            ),
        )


def seed_diet_history(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM diet_logs").fetchone()[0]
    if existing:
        return

    for log_date, day_type, calories, protein, deficit, notes in SEED_DIET_RECORDS:
        carbs = max(round((calories - (protein * 4)) * 0.65 / 4, 1), 0)
        fat = max(round((calories - (protein * 4) - (carbs * 4)) / 9, 1), 0)
        conn.execute(
            """
            INSERT INTO diet_logs (
                log_date, raw_text, calories, protein_g, carbs_g, fat_g,
                estimated_deficit_calories, meal_quality, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_date,
                f"Seeded diet history: {day_type}",
                calories,
                protein,
                carbs,
                fat,
                deficit,
                "Protein target hit" if protein >= 130 else "Protein below target",
                notes,
                datetime.now().isoformat(),
            ),
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row else {}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def get_fitness_profile() -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        row = conn.execute("SELECT * FROM fitness_profile ORDER BY id DESC LIMIT 1").fetchone()
    return row_to_dict(row)


def get_diet_context() -> dict[str, Any]:
    initialize_health_tables()
    return {
        "profile": get_fitness_profile(),
        "common_food_items": COMMON_FOOD_ITEMS,
        "diet_analysis_summary": DIET_ANALYSIS_SUMMARY,
    }


def get_weekly_split() -> dict[str, str]:
    return WEEKLY_SPLIT


def get_recent_gym_sessions(limit: int = 5) -> list[dict[str, Any]]:
    initialize_health_tables()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM gym_sessions ORDER BY session_date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return rows_to_dicts(rows)


def get_previous_sessions_by_type(session_type: str, limit: int = 3) -> list[dict[str, Any]]:
    initialize_health_tables()
    pattern = f"%{session_type}%"
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM gym_sessions
            WHERE session_type LIKE ? OR title LIKE ?
            ORDER BY session_date DESC, id DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
    return rows_to_dicts(rows)


def parse_workout_text(raw_text: str) -> dict[str, Any]:
    today = date.today()
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    raw_title = lines[0] if lines else "Workout"
    session_date = today

    duration = extract_number(raw_text, [r"Duration[:\s]+(\d+)\s*min", r"(\d+)\s*min"])
    volume = extract_number(raw_text, [r"Total Volume[:\s]+([\d,.]+)\s*kg", r"Volume[:\s]+([\d,.]+)\s*kg"])
    exercise_count = int(extract_number(raw_text, [r"Exercises?[:\s]+(\d+)"]) or 0)
    set_count = int(extract_number(raw_text, [r"Sets?[:\s]+(\d+)", r"(\d+)\s*sets?"]) or 0)
    steps = int(extract_number(raw_text, [r"Steps[:\s]+(\d+)"]) or 0)
    cardio_minutes = int(extract_number(raw_text, [r"Cardio[:\s]+(\d+)\s*min", r"(\d+)\s*min\s*cardio"]) or 0)
    cardio_distance = extract_number(raw_text, [r"([\d.]+)\s*km", r"Distance[:\s]+([\d.]+)"])

    exercises = parse_exercise_lines(lines)
    if exercises:
        set_count = set_count or len(exercises)
        exercise_count = exercise_count or len({item["exercise_name"] for item in exercises})
        volume = volume or sum((item.get("weight_kg") or 0) * (item.get("reps") or 0) for item in exercises)

    session_type = infer_session_type(raw_title)
    return {
        "session_date": session_date.isoformat(),
        "day": session_date.strftime("%A"),
        "session_type": session_type,
        "title": session_type,
        "duration_minutes": int(duration or 0),
        "total_volume_kg": float(volume or 0),
        "exercise_count": int(exercise_count or 0),
        "set_count": int(set_count or 0),
        "cardio_minutes": int(cardio_minutes or 0),
        "cardio_distance_km": float(cardio_distance or 0),
        "steps": int(steps or 0),
        "raw_text": raw_text,
        "exercises": exercises,
    }


def extract_number(text: str, patterns: list[str]) -> float:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return 0.0


def parse_exercise_lines(lines: list[str]) -> list[dict[str, Any]]:
    exercises: list[dict[str, Any]] = []
    current_exercise = ""
    set_counter: dict[str, int] = {}
    set_pattern = re.compile(
        r"(?:(left|right)\s+)?(?:set\s*)?(\d+)?\s*[:.-]?\s*([\d.]+)\s*kg\s*[xX*]\s*(\d+)",
        flags=re.IGNORECASE,
    )
    cardio_pattern = re.compile(r"([\d.]+)\s*km.*?(\d+)\s*min|(\d+)\s*min.*?([\d.]+)\s*km", flags=re.IGNORECASE)

    for line in lines:
        if re.search(r"duration|volume|workout|summary|exercises?|sets?|date", line, flags=re.IGNORECASE):
            continue
        set_match = set_pattern.search(line)
        cardio_match = cardio_pattern.search(line)
        if set_match:
            side, set_no, weight, reps = set_match.groups()
            if not current_exercise:
                current_exercise = re.sub(set_pattern, "", line).strip(" -:") or "Exercise"
            set_counter[current_exercise] = set_counter.get(current_exercise, 0) + 1
            exercises.append(
                {
                    "exercise_name": current_exercise,
                    "set_number": int(set_no or set_counter[current_exercise]),
                    "weight_kg": float(weight),
                    "reps": int(reps),
                    "distance_km": 0,
                    "time_minutes": 0,
                    "side_note": side or "",
                }
            )
        elif cardio_match:
            g = cardio_match.groups()
            distance = float(g[0] or g[3] or 0)
            minutes = float(g[1] or g[2] or 0)
            exercises.append(
                {
                    "exercise_name": current_exercise or "Cardio",
                    "set_number": 1,
                    "weight_kg": 0,
                    "reps": 0,
                    "distance_km": distance,
                    "time_minutes": minutes,
                    "side_note": "",
                }
            )
        elif len(line.split()) <= 8 and not re.search(r"\d{4}-\d{2}-\d{2}", line):
            current_exercise = line
    return exercises


def infer_session_type(title: str) -> str:
    lowered = title.lower()
    for candidate in ["push", "pull", "legs", "upper", "lower", "cardio", "arms", "shoulders", "abs"]:
        if candidate in lowered:
            return candidate.title() if candidate != "abs" else "Abs"
    return title


def save_gym_session(parsed_workout: dict[str, Any]) -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO gym_sessions (
                session_date, day, session_type, title, duration_minutes,
                total_volume_kg, exercise_count, set_count, cardio_minutes,
                cardio_distance_km, steps, raw_text, analysis, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parsed_workout.get("session_date"),
                parsed_workout.get("day"),
                parsed_workout.get("session_type"),
                parsed_workout.get("title"),
                parsed_workout.get("duration_minutes", 0),
                parsed_workout.get("total_volume_kg", 0),
                parsed_workout.get("exercise_count", 0),
                parsed_workout.get("set_count", 0),
                parsed_workout.get("cardio_minutes", 0),
                parsed_workout.get("cardio_distance_km", 0),
                parsed_workout.get("steps", 0),
                parsed_workout.get("raw_text", ""),
                parsed_workout.get("analysis", ""),
                datetime.now().isoformat(),
            ),
        )
        session_id = cursor.lastrowid
        for item in parsed_workout.get("exercises", []):
            conn.execute(
                """
                INSERT INTO gym_exercises (
                    session_id, exercise_name, set_number, weight_kg, reps,
                    distance_km, time_minutes, side_note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.get("exercise_name"),
                    item.get("set_number", 0),
                    item.get("weight_kg", 0),
                    item.get("reps", 0),
                    item.get("distance_km", 0),
                    item.get("time_minutes", 0),
                    item.get("side_note", ""),
                ),
            )
    return {"saved": True, "session_id": session_id}


def update_gym_session_analysis(session_id: int, analysis: str) -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        conn.execute("UPDATE gym_sessions SET analysis = ? WHERE id = ?", (analysis, session_id))
        updated = conn.execute("SELECT changes()").fetchone()[0]
    return {"updated": bool(updated), "session_id": session_id}


def get_gym_progress_summary() -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        df = pd.read_sql_query("SELECT * FROM gym_sessions", conn)
    if df.empty:
        return {"sessions": 0, "total_volume_kg": 0, "avg_duration_minutes": 0}
    return {
        "sessions": int(len(df)),
        "total_volume_kg": float(df["total_volume_kg"].sum()),
        "avg_duration_minutes": round(float(df["duration_minutes"].mean()), 1),
        "latest_session": df.sort_values(["session_date", "id"]).tail(1).to_dict("records")[0],
    }


def generate_gym_charts_data() -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        df = pd.read_sql_query("SELECT * FROM gym_sessions ORDER BY session_date", conn)
    if df.empty:
        return {"volume_by_date": [], "duration_by_date": [], "steps_by_date": []}
    return {
        "volume_by_date": df[["session_date", "total_volume_kg", "session_type"]].to_dict("records"),
        "duration_by_date": df[["session_date", "duration_minutes", "session_type"]].to_dict("records"),
        "steps_by_date": df[["session_date", "steps"]].to_dict("records"),
    }


def get_recent_diet_logs(limit: int = 7) -> list[dict[str, Any]]:
    initialize_health_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM diet_logs ORDER BY log_date DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return rows_to_dicts(rows)


def get_diet_logs_by_date(date: str) -> list[dict[str, Any]]:
    initialize_health_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM diet_logs WHERE log_date = ? ORDER BY id DESC", (date,)).fetchall()
    return rows_to_dicts(rows)


def save_diet_log(diet_log: dict[str, Any]) -> dict[str, Any]:
    initialize_health_tables()
    calories = int(diet_log.get("calories", 0) or 0)
    estimated_deficit = int(
        diet_log.get("estimated_deficit_calories")
        or estimate_calorie_deficit(calories, diet_log.get("log_date") or date.today().isoformat())
    )
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO diet_logs (
                log_date, raw_text, calories, protein_g, carbs_g, fat_g,
                estimated_deficit_calories, meal_quality, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                diet_log.get("log_date") or date.today().isoformat(),
                diet_log.get("raw_text", ""),
                calories,
                diet_log.get("protein_g", 0),
                diet_log.get("carbs_g", 0),
                diet_log.get("fat_g", 0),
                estimated_deficit,
                diet_log.get("meal_quality", ""),
                diet_log.get("notes", ""),
                datetime.now().isoformat(),
            ),
        )
    return {"saved": True, "diet_log_id": cursor.lastrowid}


def estimate_calorie_deficit(calories: int, log_date: str | None = None) -> int:
    parsed = pd.to_datetime(log_date, errors="coerce")
    day_name = parsed.day_name() if not pd.isna(parsed) else date.today().strftime("%A")
    planned_split = WEEKLY_SPLIT.get(day_name, "")
    maintenance_estimate = 3000 if "Rest" not in planned_split else 2600
    return max(int(maintenance_estimate - calories), 0)


def get_weight_logs(limit: int = 14) -> list[dict[str, Any]]:
    initialize_health_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM weight_logs ORDER BY log_date DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return rows_to_dicts(rows)


def save_weight_log(weight_log: dict[str, Any]) -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO weight_logs (log_date, weight_kg, steps, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                weight_log.get("log_date") or date.today().isoformat(),
                weight_log.get("weight_kg", 0),
                weight_log.get("steps", 0),
                weight_log.get("notes", ""),
                datetime.now().isoformat(),
            ),
        )
    return {"saved": True, "weight_log_id": cursor.lastrowid}


def get_diet_progress_summary() -> dict[str, Any]:
    initialize_health_tables()
    logs = get_recent_diet_logs(14)
    if not logs:
        return {"days_logged": 0, "avg_calories": 0, "avg_protein_g": 0}
    df = pd.DataFrame(logs)
    return {
        "days_logged": int(df["log_date"].nunique()),
        "avg_calories": round(float(df["calories"].mean()), 1),
        "avg_protein_g": round(float(df["protein_g"].mean()), 1),
        "avg_deficit_calories": round(float(df["estimated_deficit_calories"].fillna(0).mean()), 1)
        if "estimated_deficit_calories" in df.columns
        else 0,
    }


def estimate_diet_macros(raw_diet_text: str) -> dict[str, Any]:
    text = raw_diet_text.lower()
    calories = int(extract_number(text, [r"(\d+)\s*kcal", r"(\d+)\s*calories"]))
    protein = extract_number(text, [r"(\d+)\s*g\s*protein", r"protein[:\s]+(\d+)"])
    carbs = extract_number(text, [r"(\d+)\s*g\s*carbs?", r"carbs?[:\s]+(\d+)"])
    fat = extract_number(text, [r"(\d+)\s*g\s*fat", r"fat[:\s]+(\d+)"])
    explicit_calories = bool(calories)
    explicit_protein = bool(protein)
    explicit_carbs = bool(carbs)
    explicit_fat = bool(fat)

    matched_foods = []
    for food, macros in sorted(COMMON_FOOD_ITEMS.items(), key=lambda item: len(item[0]), reverse=True):
        if food in text:
            if any(food in matched or matched in food for matched in matched_foods):
                continue
            matched_foods.append(food)
            if not explicit_calories:
                calories += macros["calories"]
            if not explicit_protein:
                protein += macros["protein_g"]
            if not explicit_carbs:
                carbs += macros["carbs_g"]
            if not explicit_fat:
                fat += macros["fat_g"]
    if not calories:
        calories = int((protein * 4) + (carbs * 4) + (fat * 9))
        if calories < 500 and raw_diet_text.strip():
            calories += 600

    meal_quality = "High protein" if protein >= 130 else "Needs more protein add-on"
    estimated_deficit = estimate_calorie_deficit(int(calories), date.today().isoformat())
    return {
        "log_date": date.today().isoformat(),
        "raw_text": raw_diet_text,
        "calories": calories,
        "protein_g": round(protein, 1),
        "carbs_g": round(carbs, 1),
        "fat_g": round(fat, 1),
        "estimated_deficit_calories": estimated_deficit,
        "meal_quality": meal_quality,
        "notes": "Estimated from natural language; matched foods: " + ", ".join(matched_foods),
    }


def current_week_bounds() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def calculate_weekly_workout_count() -> dict[str, Any]:
    initialize_health_tables()
    week_start, week_end = current_week_bounds()
    previous_start = week_start - timedelta(days=7)
    previous_end = week_start - timedelta(days=1)
    with connect() as conn:
        current = conn.execute(
            """
            SELECT COUNT(*) FROM gym_sessions
            WHERE session_date BETWEEN ? AND ?
            """,
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()[0]
        previous = conn.execute(
            """
            SELECT COUNT(*) FROM gym_sessions
            WHERE session_date BETWEEN ? AND ?
            """,
            (previous_start.isoformat(), previous_end.isoformat()),
        ).fetchone()[0]
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "workout_count": int(current),
        "previous_week_workout_count": int(previous),
        "change_vs_previous_week": int(current - previous),
    }


def calculate_weekly_avg_protein() -> dict[str, Any]:
    initialize_health_tables()
    week_start, week_end = current_week_bounds()
    previous_start = week_start - timedelta(days=7)
    previous_end = week_start - timedelta(days=1)
    with connect() as conn:
        current = conn.execute(
            "SELECT AVG(protein_g) FROM diet_logs WHERE log_date BETWEEN ? AND ?",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()[0]
        previous = conn.execute(
            "SELECT AVG(protein_g) FROM diet_logs WHERE log_date BETWEEN ? AND ?",
            (previous_start.isoformat(), previous_end.isoformat()),
        ).fetchone()[0]
    current_avg = round(float(current or 0), 1)
    previous_avg = round(float(previous or 0), 1)
    return {
        "avg_protein_g": current_avg,
        "previous_week_avg_protein_g": previous_avg,
        "target_min_g": 130,
        "target_max_g": 150,
        "status": "on_target" if 130 <= current_avg <= 150 else "low" if current_avg < 130 else "high",
    }


def calculate_weekly_avg_calories() -> dict[str, Any]:
    initialize_health_tables()
    week_start, week_end = current_week_bounds()
    previous_start = week_start - timedelta(days=7)
    previous_end = week_start - timedelta(days=1)
    with connect() as conn:
        current = conn.execute(
            "SELECT AVG(calories), AVG(estimated_deficit_calories) FROM diet_logs WHERE log_date BETWEEN ? AND ?",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()
        previous = conn.execute(
            "SELECT AVG(calories), AVG(estimated_deficit_calories) FROM diet_logs WHERE log_date BETWEEN ? AND ?",
            (previous_start.isoformat(), previous_end.isoformat()),
        ).fetchone()
    avg_calories = round(float(current[0] or 0), 1)
    avg_deficit = round(float(current[1] or 0), 1)
    return {
        "avg_calories": avg_calories,
        "avg_deficit_calories": avg_deficit,
        "previous_week_avg_calories": round(float(previous[0] or 0), 1),
        "previous_week_avg_deficit_calories": round(float(previous[1] or 0), 1),
        "risk": "too_low" if 0 < avg_calories < 1800 else "reasonable",
    }


def calculate_weekly_avg_steps() -> dict[str, Any]:
    initialize_health_tables()
    week_start, week_end = current_week_bounds()
    with connect() as conn:
        weight_steps = conn.execute(
            "SELECT AVG(steps) FROM weight_logs WHERE log_date BETWEEN ? AND ? AND steps > 0",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()[0]
        gym_steps = conn.execute(
            "SELECT AVG(steps) FROM gym_sessions WHERE session_date BETWEEN ? AND ? AND steps > 0",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()[0]
    avg_steps = round(float(weight_steps or gym_steps or 0), 1)
    return {
        "avg_steps": avg_steps,
        "target_steps": 10000,
        "status": "on_target" if avg_steps >= 10000 else "low",
    }


def calculate_weight_trend() -> dict[str, Any]:
    initialize_health_tables()
    logs = get_weight_logs(14)
    if len(logs) < 2:
        return {"trend": "not_enough_data", "latest_weight_kg": logs[0]["weight_kg"] if logs else 0, "change_kg": 0}
    df = pd.DataFrame(logs)
    df["log_date_dt"] = pd.to_datetime(df["log_date"], errors="coerce")
    df = df.sort_values(["log_date_dt", "id"]).dropna(subset=["weight_kg"])
    if len(df) < 2:
        return {"trend": "not_enough_data", "latest_weight_kg": 0, "change_kg": 0}
    first = float(df.iloc[0]["weight_kg"] or 0)
    latest = float(df.iloc[-1]["weight_kg"] or 0)
    change = round(latest - first, 2)
    trend = "down" if change < -0.2 else "up" if change > 0.2 else "stable"
    return {
        "trend": trend,
        "latest_weight_kg": latest,
        "oldest_weight_kg": first,
        "change_kg": change,
        "days_observed": int((df.iloc[-1]["log_date_dt"] - df.iloc[0]["log_date_dt"]).days),
    }


def calculate_health_score() -> dict[str, Any]:
    workouts = calculate_weekly_workout_count()
    protein = calculate_weekly_avg_protein()
    calories = calculate_weekly_avg_calories()
    steps = calculate_weekly_avg_steps()
    weight = calculate_weight_trend()

    score = 100
    risks: list[str] = []
    if workouts["workout_count"] < 3:
        score -= 18
        risks.append("low workout frequency")
    if protein["avg_protein_g"] and protein["avg_protein_g"] < 130:
        score -= 20
        risks.append("protein below 130g/day")
    if 0 < calories["avg_calories"] < 1800:
        score -= 15
        risks.append("calories may be too low for muscle retention")
    if steps["avg_steps"] and steps["avg_steps"] < 8000:
        score -= 10
        risks.append("steps below fat-loss target")
    if weight["trend"] == "up":
        score -= 8
        risks.append("weight trending up")

    return {
        "health_score": max(score, 0),
        "risks": risks,
        "workouts": workouts,
        "protein": protein,
        "calories": calories,
        "steps": steps,
        "weight": weight,
    }


def save_health_report(report: dict[str, Any]) -> dict[str, Any]:
    initialize_health_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO health_reports (
                date, report_type, health_score, workout_summary, diet_summary,
                weight_summary, recovery_summary, recommendations, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.get("date") or date.today().isoformat(),
                report.get("report_type", "daily"),
                report.get("health_score", 0),
                report.get("workout_summary", ""),
                report.get("diet_summary", ""),
                report.get("weight_summary", ""),
                report.get("recovery_summary", ""),
                report.get("recommendations", ""),
                datetime.now().isoformat(),
            ),
        )
    return {"saved": True, "health_report_id": cursor.lastrowid}


def save_chat_message(bot_type: str, role: str, content: str) -> None:
    initialize_health_tables()
    with connect() as conn:
        conn.execute(
            "INSERT INTO chatbot_messages (bot_type, role, content, created_at) VALUES (?, ?, ?, ?)",
            (bot_type, role, content, datetime.now().isoformat()),
        )


def get_recent_chat_messages(bot_type: str, limit: int = 12) -> list[dict[str, str]]:
    initialize_health_tables()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM chatbot_messages
            WHERE bot_type = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (bot_type, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def save_tool_log(
    bot_type: str,
    tool_name: str,
    arguments: str,
    result: str = "",
    error: str = "",
) -> None:
    initialize_health_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chatbot_tool_logs (
                bot_type, tool_name, arguments, result, error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (bot_type, tool_name, arguments, result, error, datetime.now().isoformat()),
        )


def get_recent_tool_logs(bot_type: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    initialize_health_tables()
    with connect() as conn:
        if bot_type:
            rows = conn.execute(
                """
                SELECT * FROM chatbot_tool_logs
                WHERE bot_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (bot_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chatbot_tool_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return rows_to_dicts(rows)


TOOL_FUNCTIONS = {
    "get_fitness_profile": get_fitness_profile,
    "get_diet_context": get_diet_context,
    "get_weekly_split": get_weekly_split,
    "get_recent_gym_sessions": get_recent_gym_sessions,
    "get_previous_sessions_by_type": get_previous_sessions_by_type,
    "parse_workout_text": parse_workout_text,
    "save_gym_session": save_gym_session,
    "update_gym_session_analysis": update_gym_session_analysis,
    "get_gym_progress_summary": get_gym_progress_summary,
    "generate_gym_charts_data": generate_gym_charts_data,
    "get_recent_diet_logs": get_recent_diet_logs,
    "get_diet_logs_by_date": get_diet_logs_by_date,
    "save_diet_log": save_diet_log,
    "get_weight_logs": get_weight_logs,
    "save_weight_log": save_weight_log,
    "get_diet_progress_summary": get_diet_progress_summary,
    "estimate_diet_macros": estimate_diet_macros,
    "calculate_weekly_workout_count": calculate_weekly_workout_count,
    "calculate_weekly_avg_protein": calculate_weekly_avg_protein,
    "calculate_weekly_avg_calories": calculate_weekly_avg_calories,
    "calculate_weekly_avg_steps": calculate_weekly_avg_steps,
    "calculate_weight_trend": calculate_weight_trend,
    "calculate_health_score": calculate_health_score,
    "save_health_report": save_health_report,
}


def call_tool(name: str, arguments: str, bot_type: str = "") -> str:
    if name not in TOOL_FUNCTIONS:
        error = f"Unknown tool: {name}"
        save_tool_log(bot_type, name, arguments or "{}", "", error)
        return json.dumps({"error": error})
    try:
        kwargs = json.loads(arguments or "{}")
        result = TOOL_FUNCTIONS[name](**kwargs)
        result_json = json.dumps(result, default=str)
        save_tool_log(bot_type, name, arguments or "{}", result_json)
        return result_json
    except Exception as exc:
        error = str(exc)
        save_tool_log(bot_type, name, arguments or "{}", "", error)
        return json.dumps({"error": error})
