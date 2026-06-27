"""Runnable demo of the connector POC.

Exercises every path the architecture cares about, with two mock users:
  * alice -- Senior AE: salesforce read+write, jira write, all accounts
  * bob   -- Junior AE: salesforce read-only, jira write, only ACC-001

Scenarios:
  1. successful read (permission allowed)
  2. record-level permission denial (territory)
  3. successful low-risk write (auto-executed, audited)
  4. write denied (user lacks the write scope)
  5. input validation failure
  6. high-risk write -> human approval required
  7. critical write -> blocked entirely
  8. cross-system write (Jira) on the identical contract

Run:  python demo.py
(Audit records are emitted to stderr; results to stdout.)
"""
from __future__ import annotations
import json

import connectors  # noqa: F401  -- importing registers all tools
from connectors.core.registry import invoke, manifest
from connectors.core.identity import get_user


def show(title: str, result) -> None:
    print(f"\n=== {title} ===")
    print(f"status={result.status}  correlation_id={result.correlation_id}")
    if result.data is not None:
        print("data:", json.dumps(result.data, indent=2))
    if result.approval_id:
        print("approval_id:", result.approval_id, "(queued for human approval)")
    if result.error:
        print("error:", json.dumps(result.error, indent=2))


def main() -> None:
    alice = get_user("alice")
    bob = get_user("bob")

    print("# Tool manifest -- what the LLM would discover (name, kind, risk, schema):")
    print(json.dumps(manifest(), indent=2))

    show("1. Alice reads an account she owns",
         invoke("salesforce.get_account", alice, {"account_id": "ACC-001"}))

    show("2. Bob reads an account outside his territory (record-level denial)",
         invoke("salesforce.get_account", bob, {"account_id": "ACC-002"}))

    show("3. Alice creates a follow-up task (low-risk write, auto-executed)",
         invoke("salesforce.create_task", alice,
                {"account_id": "ACC-001", "task_description": "Prepare renewal deck for Acme meeting."}))

    show("4. Bob tries to create a task (no write scope -> denied)",
         invoke("salesforce.create_task", bob,
                {"account_id": "ACC-001", "task_description": "Should be blocked."}))

    show("5. Alice sends an invalid account id (validation error)",
         invoke("salesforce.get_account", alice, {"account_id": "not-an-id"}))

    show("6. Alice creates an opportunity (high-risk -> approval required)",
         invoke("salesforce.create_opportunity", alice,
                {"account_id": "ACC-001", "name": "Acme Expansion - 2026", "amount": 250000}))

    show("7. Alice tries to delete an opportunity (critical -> blocked)",
         invoke("salesforce.delete_opportunity", alice, {"opportunity_id": "OPP-1001"}))

    show("8. Alice raises a Jira escalation ticket (cross-system write)",
         invoke("jira.create_ticket", alice,
                {"summary": "Escalate Acme delivery-timeline risk",
                 "description": "Customer flagged concern about install timeline; needs ops review."}))


if __name__ == "__main__":
    main()
