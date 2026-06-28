"""Policy and authorization gate.

This is the deterministic control plane between the (untrusted) LLM's intent and
any real action. It runs AFTER input validation and the OBO exchange, and returns
exactly one decision: ALLOW, DENY, APPROVAL_REQUIRED, or BLOCK.

Decision rules (these mirror the Part 3 governance design):

    READ   -> ALLOW if the user holds the read scope for the system, else DENY.
    WRITE  -> deny-by-default; requires the write scope, then graduates by risk:
                  LOW / MEDIUM  -> ALLOW              (auto-execute, fully audited)
                  HIGH          -> APPROVAL_REQUIRED  (human-in-the-loop)
                  CRITICAL      -> BLOCK              (never executed by the AI)

A HIGH-risk write that returns APPROVAL_REQUIRED is then *routed* to a human by
the tool's ``approval_route`` (see ``ApprovalRoute`` below): the requesting rep
for actions they may perform themselves, or a distinct authorized approver for
actions that financially commit the company.

The gate can only ever *restrict* further than the user's source-system
permissions -- it never widens them.
"""
from __future__ import annotations
from enum import Enum

from .identity import DownstreamToken


class ToolKind(str, Enum):
    READ = "read"
    WRITE = "write"


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    BLOCK = "block"


class ApprovalRoute(str, Enum):
    """Who must approve a HIGH-risk write before it executes.

    SAME_USER  -- the requesting rep confirms the agent's drafted action. Used
                  when the rep is independently authorized to perform it (e.g.
                  Create Opportunity, Send Email on their own behalf). This is a
                  deliberate-action checkpoint against an over-eager or
                  misinterpreting agent -- NOT segregation of duties (requester
                  and approver are the same person by design).
    SEGREGATED -- a DISTINCT authorized approver (deal desk / manager) signs off.
                  Used when the action is financially binding or commits the
                  company to a customer (e.g. Create Quote). This IS segregation
                  of duties: a second human, not the requester, accepts the risk.
    """

    SAME_USER = "same_user"
    SEGREGATED = "segregated"


def evaluate(*, kind: ToolKind, risk: Risk, system: str, token: DownstreamToken) -> tuple[Decision, str]:
    read_scope = f"{system}.read"
    write_scope = f"{system}.write"

    if kind == ToolKind.READ:
        if read_scope in token.scopes:
            return Decision.ALLOW, "user holds read scope"
        return Decision.DENY, f"missing scope '{read_scope}'"

    # WRITE: deny-by-default, then graduate by risk.
    if write_scope not in token.scopes:
        return Decision.DENY, f"missing scope '{write_scope}'"

    if risk == Risk.CRITICAL:
        return Decision.BLOCK, "critical/irreversible action is blocked for AI execution"
    if risk == Risk.HIGH:
        return Decision.APPROVAL_REQUIRED, "high-risk write requires human approval"
    return Decision.ALLOW, "write within auto-execute risk threshold"
