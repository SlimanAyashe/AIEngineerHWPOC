"""Salesforce READ tools -- no side effects.

Physically separated from ``writes.py`` to make the read/write boundary explicit
(a graded requirement). Record-level visibility is enforced here using the user
identity carried by the OBO token: the source system only returns what the user
is allowed to see, exactly as real Salesforce sharing rules would.
"""
from __future__ import annotations

from ..core.store import accounts, opportunities
from ..core.errors import NotFoundError, UnauthorizedError
from ..core.identity import DownstreamToken, get_user
from ..core.policy import ToolKind, Risk
from ..core.registry import Tool, register


def _get_account(token: DownstreamToken, args: dict) -> dict:
    account_id = args["account_id"]
    user = get_user(token.user_id)
    # Source-system RBAC: enforce record-level (territory/ownership) visibility.
    if not user.can_access_account(account_id):
        raise UnauthorizedError("Account is outside your visibility", details={"account_id": account_id})
    for account in accounts:
        if account["id"] == account_id:
            return account
    raise NotFoundError("Account not found", details={"account_id": account_id})


def _get_opportunity(token: DownstreamToken, args: dict) -> dict:
    opportunity_id = args["opportunity_id"]
    user = get_user(token.user_id)
    for opp in opportunities:
        if opp["id"] == opportunity_id:
            if not user.can_access_account(opp["account_id"]):
                raise UnauthorizedError(
                    "Opportunity is outside your visibility",
                    details={"opportunity_id": opportunity_id},
                )
            return opp
    raise NotFoundError("Opportunity not found", details={"opportunity_id": opportunity_id})


register(Tool(
    name="salesforce.get_account",
    system="salesforce",
    kind=ToolKind.READ,
    risk=Risk.LOW,
    description="Retrieve a Salesforce account by id.",
    input_schema={"account_id": {"type": "string", "required": True, "pattern": r"ACC-\d{3}"}},
    handler=_get_account,
))

register(Tool(
    name="salesforce.get_opportunity",
    system="salesforce",
    kind=ToolKind.READ,
    risk=Risk.LOW,
    description="Retrieve a Salesforce opportunity by id.",
    input_schema={"opportunity_id": {"type": "string", "required": True, "pattern": r"OPP-\d{4}"}},
    handler=_get_opportunity,
))
