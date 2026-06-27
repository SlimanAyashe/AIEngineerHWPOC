"""Append-only audit logging.

Every tool invocation produces a structured, attributable record: who (the real
user identity carried by the OBO token), what tool, what inputs, the policy
decision, and the outcome. In production these flow to an immutable sink
(Azure Log Analytics -> Microsoft Sentinel). Here we echo them and keep them in
memory so the demo and tests can inspect the trail.
"""
from __future__ import annotations
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditRecord:
    correlation_id: str
    user_id: str
    tool: str
    kind: str
    event: str                      # "decision" | "result"
    decision: str | None = None     # allow | deny | approval_required | block
    status: str | None = None       # ok | pending_approval | error
    args: dict | None = None
    detail: dict | None = None
    timestamp: str = field(default_factory=_now)


class AuditLog:
    def __init__(self, echo: bool = True):
        self.records: list[AuditRecord] = []
        self.echo = echo

    def record(self, rec: AuditRecord) -> None:
        self.records.append(rec)
        if self.echo:
            # stderr keeps the audit stream separate from program output (stdout).
            print(f"AUDIT {json.dumps(asdict(rec), default=str)}", file=sys.stderr)

    def clear(self) -> None:
        self.records.clear()


# Module-level singleton for the POC.
audit_log = AuditLog()
