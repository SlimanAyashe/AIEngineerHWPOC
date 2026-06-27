"""Salesforce WRITE tools -- mutating operations.

Deny-by-default at the policy gate and graduated by risk:

    create_task        -> LOW      (auto-execute, audited)
    create_opportunity -> HIGH     (human approval required before execution)
    delete_opportunity -> CRITICAL (blocked entirely for AI execution)

Keeping writes in their own module makes the highest-risk surface easy to review
in isolation.
"""
from __future__ import annotations
from datetime import datetime, timezone

from ..core.store import accounts, opportunities, tasks
from ..core.errors import NotFoundError, UnauthorizedError
from ..core.identity import DownstreamToken, get_user
from ..core.policy import ToolKind, Risk
from ..core.registry import Tool, register


def _next_id(prefix: str, seq: list[dict]) -> str:
    return f"{prefix}-{len(seq) + 1:04d}"


def _create_task(token: DownstreamToken, args: dict) -> dict:
    account_id = args["account_id"]
    user = get_user(token.user_id)
    if not user.can_access_account(account_id):
        raise UnauthorizedError("Account is outside your visibility", details={"account_id": account_id})
    if not any(a["id"] == account_id for a in accounts):
        raise NotFoundError("Account not found", details={"account_id": account_id})

    task = {
        "id": _next_id("TASK", tasks),
        "account_id": account_id,
        "description": args["task_description"],
        "created_by": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "open",
    }
    tasks.append(task)  # mock persistence
    return task


def _create_opportunity(token: DownstreamToken, args: dict) -> dict:
    # Only reached AFTER human approval (policy classifies this as HIGH risk).
    # Shown for completeness of the write path.
    user = get_user(token.user_id)
    opp = {
        "id": _next_id("OPP", opportunities),
        "account_id": args["account_id"],
        "name": args["name"],
        "amount": args["amount"],
        "stage": "Prospecting",
        "owner": user.id,
    }
    opportunities.append(opp)
    return opp


def _delete_opportunity(token: DownstreamToken, args: dict) -> dict:
    # Registered as CRITICAL -> the policy gate BLOCKS before this ever runs.
    # Present only so the destructive capability is explicit and visibly governed.
    raise RuntimeError("unreachable: delete_opportunity is blocked by policy")


register(Tool(
    name="salesforce.create_task",
    system="salesforce",
    kind=ToolKind.WRITE,
    risk=Risk.LOW,
    description="Create a follow-up task on an account.",
    input_schema={
        "account_id": {"type": "string", "required": True, "pattern": r"ACC-\d{3}"},
        "task_description": {"type": "string", "required": True, "min_length": 3, "max_length": 500},
    },
    handler=_create_task,
))

register(Tool(
    name="salesforce.create_opportunity",
    system="salesforce",
    kind=ToolKind.WRITE,
    risk=Risk.HIGH,
    description="Create a new sales opportunity (requires human approval).",
    input_schema={
        "account_id": {"type": "string", "required": True, "pattern": r"ACC-\d{3}"},
        "name": {"type": "string", "required": True, "min_length": 3, "max_length": 120},
        "amount": {"type": "number", "required": True, "min": 0},
    },
    handler=_create_opportunity,
))

register(Tool(
    name="salesforce.delete_opportunity",
    system="salesforce",
    kind=ToolKind.WRITE,
    risk=Risk.CRITICAL,
    description="Delete an opportunity (blocked for AI execution).",
    input_schema={"opportunity_id": {"type": "string", "required": True, "pattern": r"OPP-\d{4}"}},
    handler=_delete_opportunity,
))
