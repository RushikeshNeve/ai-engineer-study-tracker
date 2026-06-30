# AI Engineer Study Tracker

A simple local Streamlit app for tracking a 6-month Backend + AI Engineer transition plan.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

For the coach bots, set your OpenAI API key before running Streamlit:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

For Streamlit Cloud, add the same key in the app secrets:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

## Run

```bash
streamlit run app.py
```

The app automatically creates `study_tracker.db` in the project folder.

## Deploy to Streamlit Cloud

1. Push this repository to GitHub.
2. Open Streamlit Community Cloud and create a new app from the GitHub repository.
3. Select branch `main` and main file `app.py`.
4. Add `OPENAI_API_KEY` in the app secrets.
5. Deploy the app.

The local SQLite database file is ignored by Git. On deployment, the app creates a fresh `study_tracker.db` automatically and seeds the default study, backend, system design, gym, and diet data.

## Features

- Dashboard with today's schedule, planned study slots, weekly metrics, progress bars, and charts.
- Daily logs for study slots, study minutes, DSA count, gym, steps, mood, blockers, and reflection.
- DSA tracker with topic, pattern, difficulty, platform, confidence, mistakes, and revision dates.
- AI cohort tracker with auto-calculated completion percentage.
- System design tracker for requirements, HLD, database design, scaling, and tradeoffs.
- System design course tracker with 25 preloaded sections, phase progress, confidence charts, study-hour charts, revision tracking, and interview readiness.
- Backend deep dive tracker for topics, resources, implementation, confidence, and notes.
- Backend course tracker with preloaded backend engineering phases, topic progress, implementation ideas, revision tracking, and interview readiness.
- Projects tracker with progress bars, links, tasks, blockers, and notes.
- Notes and learnings page with search across title, content, and tags.
- Weekly review page for wins, misses, hours, DSA count, backend course progress, project progress, learnings, focus, and burnout.
- Health dashboard for weight, gym volume, cardio, steps, split adherence, and latest coach analyses.
- Gym tracker and OpenAI-based Gym Coach Bot with SQLite-backed tool calling.
- Diet tracker and OpenAI-based Diet Coach Bot with macro estimation and SQLite-backed tool calling.
- Calorie deficit tracking with diet line charts for calories, protein, deficit, macros, and weekly trends.
- Weight and steps tracker.
- CSV export for every table and Excel export when `openpyxl` is installed.

## Coach Bots

The Gym Coach Bot and Diet Coach Bot use OpenAI tool/function calling. The model receives JSON schemas, calls internal Python tools, those tools read/write SQLite, and the final answer is generated after tool results are returned.

Each bot page includes a recent tool log expander so you can inspect which Python tools were called, the JSON arguments, and the returned results. Gym coach final analysis is also saved back to the matching `gym_sessions.analysis` row.

The Diet Coach Bot is seeded with Rushikesh's nutrition context: eggetarian diet pattern, 130-150g protein target, training/rest-day calorie targets, water target, common protein add-ons, and previous diet records.

Gym Coach Bot test:

```text
Push Workout
2026-06-29
Duration: 45 min
Total Volume: 5000 kg
Sets: 10
Bench Press
1 60 kg x 10
2 65 kg x 8
Cardio 10 min 1.2 km
```

Diet Coach Bot test:

```text
Breakfast: 3 eggs and oats. Lunch: chicken, rice, curd. Evening: whey protein. Dinner: paneer and roti.
```

## Backend Course Tracker

The Backend Course Tracker follows the backend engineering course at:

```text
https://youtu.be/0Rwb4Xmlcwc?si=TDG5hZDWn0HAriFR
```

It preloads the course into six phases: fundamentals, databases, caching/performance, distributed systems, security/reliability, and production/deployment. Use it to mark videos, notes, mini implementations, confidence, revision dates, and interview readiness topic by topic.

## System Design Course Tracker

The System Design Course Tracker preloads 25 sections across four phases:

- Fundamentals
- Blueprint
- Case Studies
- Revision

Sections 1-4 are marked completed by default. Use the tracker to update status, confidence, notes, diagrams, implementation practice, study hours, revision dates, and interview readiness.

## Future Improvements

- Add edit and delete actions for existing rows.
- Add calendar-style weekly and monthly views.
- Add recurring DSA revision reminders.
- Add import from CSV.
- Add richer analytics for track balance and consistency trends.
