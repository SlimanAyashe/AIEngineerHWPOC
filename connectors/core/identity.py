"""Identity and simulated On-Behalf-Of (OBO) token exchange.

In production this is real OAuth2: the user signs in via Microsoft Entra ID, and
each connector exchanges the user's access token for a *downstream* token scoped
to the target system (Salesforce API, Microsoft Graph for SharePoint, Jira) using
the OAuth2 On-Behalf-Of grant. The downstream token represents THE USER, so every
source system enforces that user's own permissions.

Here we simulate the exchange with an in-memory directory. The property we keep
faithful to production: the connector only ever acts with the *user's* delegated
identity and scopes -- never a god-mode service account. This is what makes "the
agent can never exceed the logged-in user" true in code.
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
    """Simulate the OAuth2 On-Behalf-Of grant for one downstream system.

    Real flow: POST to the Entra ID token endpoint with
    ``grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer``, the user's token
    as the assertion, and the target resource/scope. Entra returns a token scoped
    to that resource, acting as the user. We approximate by projecting the user's
    delegated scopes for ``system``; absence of any scope means no access.
    """
    system_scopes = frozenset(s for s in user.scopes if s.startswith(f"{system}."))
    if not system_scopes:
        raise UnauthorizedError(
            f"User has no delegated access to {system}",
            details={"user_id": user.id, "system": system},
        )
    return DownstreamToken(user_id=user.id, system=system, scopes=system_scopes)
