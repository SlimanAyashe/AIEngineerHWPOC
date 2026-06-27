"""In-memory mock data store, loaded from JSON.

Stands in for the real systems of record. Reads query these lists; writes append
to them (mock persistence for the lifetime of the process). Swapping these for
real API calls is the only change needed to go from POC to integration.
"""
from __future__ import annotations
import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> list[dict]:
    with open(_DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


accounts: list[dict] = _load("accounts.json")
opportunities: list[dict] = _load("opportunities.json")
tasks: list[dict] = _load("tasks.json")
jira_tickets: list[dict] = _load("jira_tickets.json")
