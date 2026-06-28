"""Identity and simulated per-user "act-as-user" token exchange.

In production the user signs in once via Microsoft Entra ID, and each connector
obtains a *downstream* token that represents THE USER for its target system. The
exact mechanism differs by system -- this is deliberately abstracted behind one
``obo_exchange`` seam here, but it is NOT one uniform call in reality:

  * SharePoint (via Microsoft Graph): a true Entra ID **OAuth2 On-Behalf-Of**
    grant (``grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer``) exchanges
    the user's token for a Graph token acting as the user.
  * Salesforce: its own OAuth authorization server. Entra federates *sign-in*
    (SSO); the connector then brokers a per-user Salesforce token (e.g. SAML-
    bearer assertion flow / connected app). Entra OBO does not itself mint a
    Salesforce API token.
  * Jira (Atlassian): likewise its own IdP/authz server (Atlassian 3LO). A
    per-connector delegated OAuth flow brokers a per-user token.

The principle is identical across all three and is what we keep faithful in code:
the connector only ever acts with the *user's* delegated identity and scopes --
never a god-mode service account. That is what makes "the agent can never exceed
the logged-in user" true. Here we simulate every variant with an in-memory
directory; only the token-minting plumbing differs in production.
"""
from __future__ import annotations
from dataclasses import dataclass

from .errors import UnauthorizedError


@dataclass(frozen=True)
class User:
    id: str
    name: str
    scopes: frozenset[str]          # delegated permissions, e.g. "salesforce.read"
    account_access: frozenset[str]  # record-level access; "*" means all accounts

    def can_access_account(self, account_id: str) -> bool:
        return "*" in self.account_access or account_id in self.account_access


@dataclass(frozen=True)
class DownstreamToken:
    """Mock of the OBO-exchanged token used to call a single downstream system."""

    user_id: str
    system: str
    scopes: frozenset[str]


# Mock user directory -- stands in for Entra ID plus per-system role assignments.
DIRECTORY: dict[str, User] = {
    "alice": User(
        id="alice",
        name="Alice Rep (Senior AE)",
        scopes=frozenset({"salesforce.read", "salesforce.write", "jira.write"}),
        account_access=frozenset({"*"}),
    ),
    "bob": User(
        id="bob",
        name="Bob Rep (Junior AE)",
        # No salesforce.write -> writes will be denied at the policy gate.
        scopes=frozenset({"salesforce.read", "jira.write"}),
        # Limited territory -> can only see ACC-001 at the record level.
        account_access=frozenset({"ACC-001"}),
    ),
}


def get_user(user_id: str) -> User:
    user = DIRECTORY.get(user_id)
    if user is None:
        raise UnauthorizedError("Unknown or unauthenticated user", details={"user_id": user_id})
    return user


def obo_exchange(user: User, system: str) -> DownstreamToken:
    """Simulate the per-user "act-as-user" token exchange for one downstream system.

    Real flow depends on the system (see module docstring): a true Entra ID OBO
    jwt-bearer grant for Microsoft Graph/SharePoint, or a per-connector delegated
    OAuth token broker for Salesforce and Jira (which are their own authorization
    servers). All three yield a token that acts as the user. We approximate by
    projecting the user's delegated scopes for ``system``; absence of any scope
    means no access.
    """
    system_scopes = frozenset(s for s in user.scopes if s.startswith(f"{system}."))
    if not system_scopes:
        raise UnauthorizedError(
            f"User has no delegated access to {system}",
            details={"user_id": user.id, "system": system},
        )
    return DownstreamToken(user_id=user.id, system=system, scopes=system_scopes)
