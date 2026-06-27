"""Tool registry, MCP-style manifest, and the single invocation pipeline.

``invoke()`` is the ONE entry point an agent uses to call any tool. It enforces
the full pipeline, in order:

    validate input -> OBO token exchange -> policy gate -> (approval?) -> execute

and audits every decision and result. Read and write tools are registered from
physically separate modules (``salesforce/reads.py`` vs ``salesforce/writes.py``)
but share this uniform contract -- so adding Jira, SharePoint, or any other system
is just another descriptor, never a new control path.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Callable

from .audit import audit_log, AuditRecord
from .errors import ConnectorError, NotFoundError, UnauthorizedError, PolicyBlockedError
from .identity import User, DownstreamToken, obo_exchange
from .policy import ToolKind, Risk, Decision, evaluate
from .validation import validate


@dataclass(frozen=True)
class Tool:
    name: str
    system: str
    kind: ToolKind
    risk: Risk
    description: str
    input_schema: dict
    handler: Callable[[DownstreamToken, dict], dict]


_REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    if tool.name in _REGISTRY:
        raise ValueError(f"duplicate tool registration: {tool.name}")
    _REGISTRY[tool.name] = tool


def manifest() -> list[dict]:
    """MCP-style descriptor list an LLM would use to discover available tools."""
    return [
        {
            "name": t.name,
            "system": t.system,
            "kind": t.kind.value,
            "risk": t.risk.value,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in _REGISTRY.values()
    ]


@dataclass
class Result:
    status: str                       # "ok" | "pending_approval" | "error"
    data: dict | None = None
    error: dict | None = None
    approval_id: str | None = None
    correlation_id: str | None = None


def _approval_ticket() -> str:
    return "APR-" + uuid.uuid4().hex[:8]


def invoke(tool_name: str, user: User, args: dict, correlation_id: str | None = None) -> Result:
    """Single, audited entry point for every tool call."""
    cid = correlation_id or "REQ-" + uuid.uuid4().hex[:8]

    tool = _REGISTRY.get(tool_name)
    if tool is None:
        raise NotFoundError("Unknown tool", details={"tool": tool_name})

    try:
        # 1. Validate input against the tool schema (reject unexpected/invalid args).
        clean = validate(tool.input_schema, args)

        # 2. OBO exchange: obtain a downstream token scoped to this system, acting
        #    as the user. Raises Unauthorized if the user has no access at all.
        token = obo_exchange(user, tool.system)

        # 3. Policy gate: deterministic allow / deny / approval / block decision.
        decision, reason = evaluate(kind=tool.kind, risk=tool.risk, system=tool.system, token=token)
        audit_log.record(AuditRecord(
            correlation_id=cid, user_id=user.id, tool=tool.name, kind=tool.kind.value,
            event="decision", decision=decision.value, args=clean, detail={"reason": reason},
        ))

        if decision == Decision.BLOCK:
            raise PolicyBlockedError(f"Tool '{tool.name}' is blocked for AI execution", details={"reason": reason})
        if decision == Decision.DENY:
            raise UnauthorizedError(f"Not permitted to call '{tool.name}'", details={"reason": reason})
        if decision == Decision.APPROVAL_REQUIRED:
            approval_id = _approval_ticket()
            # In production: enqueue to Azure Service Bus, notify the approver, and
            # execute the handler only after an authorized human approves.
            audit_log.record(AuditRecord(
                correlation_id=cid, user_id=user.id, tool=tool.name, kind=tool.kind.value,
                event="result", status="pending_approval", detail={"approval_id": approval_id},
            ))
            return Result(status="pending_approval", approval_id=approval_id, correlation_id=cid)

        # 4. Execute the handler with the user's delegated token.
        data = tool.handler(token, clean)
        audit_log.record(AuditRecord(
            correlation_id=cid, user_id=user.id, tool=tool.name, kind=tool.kind.value,
            event="result", status="ok",
        ))
        return Result(status="ok", data=data, correlation_id=cid)

    except ConnectorError as e:
        # Typed errors become a consistent envelope; internals never leak out.
        audit_log.record(AuditRecord(
            correlation_id=cid, user_id=user.id, tool=tool.name, kind=tool.kind.value,
            event="result", status="error", detail=e.to_envelope(),
        ))
        return Result(status="error", error=e.to_envelope(), correlation_id=cid)
