"""Typed errors for the connector layer.

Every error carries a machine-readable ``code`` and a safe ``message``. At the
boundary (see ``registry.invoke``) errors are converted to a consistent envelope,
so the agent/LLM and the end user never receive stack traces or internal details.
"""
from __future__ import annotations


class ConnectorError(Exception):
    """Base class. Subclasses set ``code`` and an HTTP-ish status for mapping."""

    code = "connector_error"
    http_status = 500

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_envelope(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationError(ConnectorError):
    """Input failed schema validation (bad/missing/unexpected fields)."""

    code = "validation_error"
    http_status = 400


class NotFoundError(ConnectorError):
    """Requested record does not exist."""

    code = "not_found"
    http_status = 404


class UnauthorizedError(ConnectorError):
    """User lacks the scope or record-level permission for this action."""

    code = "unauthorized"
    http_status = 403


class PolicyBlockedError(ConnectorError):
    """Tool is blocked from AI execution by governance policy."""

    code = "policy_blocked"
    http_status = 403
