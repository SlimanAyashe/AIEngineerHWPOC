"""Jira WRITE tool -- a second system on the identical tool contract.

Demonstrates that the read/write separation, OBO exchange, policy gate, and audit
trail generalize across systems with no new control path. A Jira ticket is
internal, reversible, and low blast radius -> LOW risk (auto-execute, audited);
in production it would still be rate-limited and fully attributable.
"""
from __future__ import annotations
from datetime import datetime, timezone

from ..core.store import jira_tickets
from ..core.identity import DownstreamToken, get_user
from ..core.policy import ToolKind, Risk
from ..core.registry import Tool, register


def _create_ticket(token: DownstreamToken, args: dict) -> dict:
    user = get_user(token.user_id)
    ticket = {
        "key": f"SALES-{len(jira_tickets) + 101}",
        "summary": args["summary"],
        "description": args.get("description", ""),
        "reporter": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "To Do",
    }
    jira_tickets.append(ticket)  # mock persistence
    return ticket


register(Tool(
    name="jira.create_ticket",
    system="jira",
    kind=ToolKind.WRITE,
    risk=Risk.LOW,
    description="Create a Jira ticket for an internal team (e.g. support or escalation).",
    input_schema={
        "summary": {"type": "string", "required": True, "min_length": 3, "max_length": 200},
        "description": {"type": "string", "required": False, "max_length": 2000},
    },
    handler=_create_ticket,
))
