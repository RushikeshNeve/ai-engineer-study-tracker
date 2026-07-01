from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DB_PATH = Path("study_tracker.db")
GITHUB_API = "https://api.github.com"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def initialize_github_tables() -> None:
    with connect() as conn:
        conn.executescript(
            """
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
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_github_activity_unique "
            "ON github_activity(repo_name, activity_type, url)"
        )


def github_token() -> str:
    return os.getenv("GITHUB_TOKEN", "").strip()


def github_is_configured() -> bool:
    return bool(github_token())


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mythos-streamlit-tracker",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_request(path: str, params: dict[str, Any] | None = None) -> Any:
    if not github_is_configured():
        raise RuntimeError("GITHUB_TOKEN is missing. Add it to your environment to sync GitHub data.")
    url = f"{GITHUB_API}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc


def get_authenticated_user() -> dict[str, Any]:
    return github_request("/user")


def get_user_repositories(username: str | None = None) -> list[dict[str, Any]]:
    if username:
        repos = github_request(f"/users/{username}/repos", {"per_page": 100, "sort": "pushed", "direction": "desc"})
    else:
        repos = github_request("/user/repos", {"per_page": 100, "sort": "pushed", "direction": "desc", "affiliation": "owner,collaborator"})
    return [normalize_repository(repo) for repo in repos]


def normalize_repository(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo_name": repo.get("full_name") or repo.get("name") or "",
        "repo_url": repo.get("html_url") or "",
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "stars": int(repo.get("stargazers_count") or 0),
        "forks": int(repo.get("forks_count") or 0),
        "last_pushed_at": repo.get("pushed_at") or "",
    }


def save_repositories(repositories: list[dict[str, Any]]) -> None:
    initialize_github_tables()
    now = datetime.now().isoformat()
    with connect() as conn:
        for repo in repositories:
            if not repo.get("repo_name"):
                continue
            conn.execute(
                """
                INSERT INTO github_repositories (
                    repo_name, repo_url, description, language, stars,
                    forks, last_pushed_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_name) DO UPDATE SET
                    repo_url = excluded.repo_url,
                    description = excluded.description,
                    language = excluded.language,
                    stars = excluded.stars,
                    forks = excluded.forks,
                    last_pushed_at = excluded.last_pushed_at
                """,
                (
                    repo.get("repo_name", ""),
                    repo.get("repo_url", ""),
                    repo.get("description", ""),
                    repo.get("language", ""),
                    int(repo.get("stars", 0) or 0),
                    int(repo.get("forks", 0) or 0),
                    repo.get("last_pushed_at", ""),
                    now,
                ),
            )


def get_repository_details(repo_name: str) -> dict[str, Any]:
    initialize_github_tables()
    with connect() as conn:
        row = conn.execute("SELECT * FROM github_repositories WHERE repo_name = ?", (repo_name,)).fetchone()
    if row:
        return dict(row)
    repo = normalize_repository(github_request(f"/repos/{repo_name}"))
    save_repositories([repo])
    return repo


def get_recent_commits(repo_name: str, limit: int = 10) -> list[dict[str, Any]]:
    commits = github_request(f"/repos/{repo_name}/commits", {"per_page": max(1, min(limit, 50))})
    results = []
    for commit in commits:
        commit_data = commit.get("commit") or {}
        author = commit_data.get("author") or {}
        results.append(
            {
                "repo_name": repo_name,
                "activity_type": "commit",
                "title": (commit_data.get("message") or "").splitlines()[0],
                "url": commit.get("html_url") or "",
                "activity_date": author.get("date") or "",
                "metadata": {
                    "sha": commit.get("sha"),
                    "author": (commit.get("author") or {}).get("login") or author.get("name"),
                },
            }
        )
    return results


def get_recent_pull_requests(repo_name: str, limit: int = 10) -> list[dict[str, Any]]:
    pulls = github_request(
        f"/repos/{repo_name}/pulls",
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": max(1, min(limit, 50))},
    )
    return [
        {
            "repo_name": repo_name,
            "activity_type": "pull_request",
            "title": pull.get("title") or "",
            "url": pull.get("html_url") or "",
            "activity_date": pull.get("updated_at") or pull.get("created_at") or "",
            "metadata": {"state": pull.get("state"), "number": pull.get("number"), "merged_at": pull.get("merged_at")},
        }
        for pull in pulls
    ]


def get_recent_issues(repo_name: str, limit: int = 10) -> list[dict[str, Any]]:
    issues = github_request(
        f"/repos/{repo_name}/issues",
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": max(1, min(limit, 50))},
    )
    results = []
    for issue in issues:
        if issue.get("pull_request"):
            continue
        results.append(
            {
                "repo_name": repo_name,
                "activity_type": "issue",
                "title": issue.get("title") or "",
                "url": issue.get("html_url") or "",
                "activity_date": issue.get("updated_at") or issue.get("created_at") or "",
                "metadata": {"state": issue.get("state"), "number": issue.get("number")},
            }
        )
    return results


def save_activity(items: list[dict[str, Any]]) -> None:
    initialize_github_tables()
    now = datetime.now().isoformat()
    with connect() as conn:
        for item in items:
            if not item.get("repo_name") or not item.get("url"):
                continue
            conn.execute(
                """
                INSERT INTO github_activity (
                    repo_name, activity_type, title, url, activity_date,
                    metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_name, activity_type, url) DO UPDATE SET
                    title = excluded.title,
                    activity_date = excluded.activity_date,
                    metadata_json = excluded.metadata_json
                """,
                (
                    item.get("repo_name", ""),
                    item.get("activity_type", ""),
                    item.get("title", ""),
                    item.get("url", ""),
                    item.get("activity_date", ""),
                    json.dumps(item.get("metadata", {})),
                    now,
                ),
            )


def sync_github_activity(username: str | None = None, repo_limit: int = 20, activity_limit: int = 10) -> dict[str, Any]:
    initialize_github_tables()
    repositories = get_user_repositories(username)
    repositories = repositories[: max(1, min(repo_limit, 100))]
    save_repositories(repositories)

    activity: list[dict[str, Any]] = []
    errors: list[str] = []
    for repo in repositories:
        repo_name = repo.get("repo_name", "")
        try:
            activity.extend(get_recent_commits(repo_name, activity_limit))
            activity.extend(get_recent_pull_requests(repo_name, activity_limit))
            activity.extend(get_recent_issues(repo_name, activity_limit))
        except RuntimeError as exc:
            errors.append(f"{repo_name}: {exc}")
    save_activity(activity)
    return {
        "synced": True,
        "repositories": len(repositories),
        "activity_items": len(activity),
        "errors": errors,
    }


def list_saved_repositories() -> list[dict[str, Any]]:
    initialize_github_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM github_repositories ORDER BY last_pushed_at DESC, repo_name").fetchall()
    return rows_to_dicts(rows)


def list_recent_activity(limit: int = 50, repo_name: str | None = None) -> list[dict[str, Any]]:
    initialize_github_tables()
    with connect() as conn:
        if repo_name and repo_name != "All":
            rows = conn.execute(
                "SELECT * FROM github_activity WHERE repo_name = ? ORDER BY activity_date DESC, id DESC LIMIT ?",
                (repo_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM github_activity ORDER BY activity_date DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return rows_to_dicts(rows)


def github_weekly_summary(week_start: str | None = None, week_end: str | None = None) -> dict[str, Any]:
    initialize_github_tables()
    today = date.today()
    start = date.fromisoformat(week_start) if week_start else today - timedelta(days=today.weekday())
    end = date.fromisoformat(week_end) if week_end else start + timedelta(days=6)
    start_text, end_text = start.isoformat(), end.isoformat()
    with connect() as conn:
        activity = rows_to_dicts(
            conn.execute(
                """
                SELECT * FROM github_activity
                WHERE substr(activity_date, 1, 10) BETWEEN ? AND ?
                ORDER BY activity_date DESC
                """,
                (start_text, end_text),
            ).fetchall()
        )
        repos = rows_to_dicts(conn.execute("SELECT * FROM github_repositories ORDER BY last_pushed_at DESC").fetchall())
    commit_count = sum(1 for item in activity if item.get("activity_type") == "commit")
    pr_count = sum(1 for item in activity if item.get("activity_type") == "pull_request")
    issue_count = sum(1 for item in activity if item.get("activity_type") == "issue")
    repo_counts: dict[str, int] = {}
    for item in activity:
        repo_counts[item.get("repo_name", "")] = repo_counts.get(item.get("repo_name", ""), 0) + 1
    active_repo = max(repo_counts, key=repo_counts.get) if repo_counts else (repos[0]["repo_name"] if repos else "")
    last_pushed_repo = repos[0]["repo_name"] if repos else ""
    return {
        "week_start": start_text,
        "week_end": end_text,
        "commits": commit_count,
        "pull_requests": pr_count,
        "issues": issue_count,
        "activity_items": len(activity),
        "active_repo": active_repo,
        "last_pushed_repo": last_pushed_repo,
        "repositories": len(repos),
        "recent_activity": activity[:10],
    }


def github_activity_trend(days: int = 14) -> list[dict[str, Any]]:
    initialize_github_tables()
    start = date.today() - timedelta(days=max(1, days - 1))
    with connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT substr(activity_date, 1, 10) AS activity_day,
                       activity_type,
                       COUNT(*) AS count
                FROM github_activity
                WHERE substr(activity_date, 1, 10) >= ?
                GROUP BY activity_day, activity_type
                ORDER BY activity_day
                """,
                (start.isoformat(),),
            ).fetchall()
        )
    return rows


def link_github_to_projects() -> list[dict[str, Any]]:
    initialize_github_tables()
    with connect() as conn:
        repos = rows_to_dicts(conn.execute("SELECT * FROM github_repositories").fetchall())
        projects = rows_to_dicts(conn.execute("SELECT id, project_name, github_link FROM projects").fetchall())
    links = []
    for repo in repos:
        repo_url = str(repo.get("repo_url", "")).lower()
        repo_name = str(repo.get("repo_name", "")).lower()
        for project in projects:
            project_link = str(project.get("github_link", "")).lower()
            project_name = str(project.get("project_name", "")).lower().replace(" ", "-")
            if project_link and (repo_url in project_link or project_link in repo_url):
                links.append({"repo_name": repo.get("repo_name"), "project_id": project.get("id"), "project_name": project.get("project_name")})
            elif project_name and project_name in repo_name:
                links.append({"repo_name": repo.get("repo_name"), "project_id": project.get("id"), "project_name": project.get("project_name")})
    return links
