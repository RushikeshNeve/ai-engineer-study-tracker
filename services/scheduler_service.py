from __future__ import annotations

from typing import Callable

from services.automation_engine import run_due_automations


def tick(ai_runner: Callable[[str], str], limit: int = 3) -> list[dict]:
    return run_due_automations(ai_runner, limit=limit)
