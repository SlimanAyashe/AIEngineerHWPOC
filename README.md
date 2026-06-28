# Part 2 — Connector / Tool POC

A small, runnable proof of concept for how enterprise systems (Salesforce, Jira,
SharePoint) are exposed to an AI agent **safely**. It makes the Part 1 architecture
and the Part 3 governance model concrete in code.

- **No setup, no accounts, no keys.** Pure Python standard library, mock data.
- **Salesforce** and **Jira** are fully implemented; **SharePoint** is a registered
  stub (handler deferred, contract intact) — the brief explicitly allows this.

```bash
# from this poc/ directory (Python 3.10+)
python demo.py            # walk through 8 scenarios end to end
python -m unittest -v     # 11 smoke tests, no dependencies
```

## What this POC demonstrates (maps to the grading criteria)

| Requirement | Where it lives |
|-------------|----------------|
| **Clear API / tool structure** | Uniform `Tool` contract + MCP-style `manifest()` in [registry.py](connectors/core/registry.py) |
| **Read/write separation** | Physically separate modules: [reads.py](connectors/salesforce/reads.py) vs [writes.py](connectors/salesforce/writes.py), tagged `ToolKind.READ`/`WRITE` |
| **Input validation** | Schema-driven [validation.py](connectors/core/validation.py) (rejects bad types, patterns, and unexpected fields) |
| **Error handling** | Typed errors in [errors.py](connectors/core/errors.py) → one consistent `Result` envelope; no stack traces leak |
| **Logging / audit** | Structured, attributable records in [audit.py](connectors/core/audit.py) on every decision and result |
| **OBO + per-user permissions** | Simulated OBO token exchange + scopes + record-level access in [identity.py](connectors/core/identity.py) |
| **Governance (Part 3) in code** | Risk-graduated policy gate in [policy.py](connectors/core/policy.py): allow / deny / **approval** / **block** |

## The one pipeline every call goes through

`registry.invoke()` is the single entry point. There is **no path** to a system that
skips it:

```
validate input → OBO token exchange → policy gate → (human approval?) → execute
        │               │                  │                              │
        └── all four steps are audited with the real user identity ───────┘
```

This is the codified version of the two architecture principles:
1. **The agent never exceeds the logged-in user** — every call runs under the user's
   OBO-delegated token and scopes; the source system enforces record visibility.
2. **The LLM is untrusted** — it only chooses a tool + args; the deterministic gate
   (not the model) decides whether anything actually happens.

## Scenarios in `demo.py`

| # | Call | Outcome | Proves |
|---|------|---------|--------|
| 1 | Alice reads ACC-001 | `ok` | Permitted read under OBO |
| 2 | Bob reads ACC-002 | `unauthorized` | Record-level territory enforcement |
| 3 | Alice creates a task | `ok` | Low-risk write auto-executes (audited) |
| 4 | Bob creates a task | `unauthorized` | Missing `salesforce.write` scope → deny |
| 5 | Alice sends bad id | `validation_error` | Input validation at the boundary |
| 6 | Alice creates opportunity | `pending_approval` | High-risk write → human-in-the-loop |
| 7 | Alice deletes opportunity | `policy_blocked` | Critical action blocked from AI entirely |
| 8 | Alice creates Jira ticket | `ok` | Same contract generalizes across systems |

(Users: **alice** = senior AE, full access; **bob** = junior AE, read-only Salesforce
and a single-account territory.)

## Layout

```
poc/
├── demo.py                     # runnable walkthrough (8 scenarios)
├── test_connectors.py          # 11 stdlib unittests
└── connectors/
    ├── __init__.py             # importing registers all tools
    ├── core/
    │   ├── registry.py         # Tool contract, manifest, invoke() pipeline
    │   ├── policy.py           # risk-graduated allow/deny/approval/block gate
    │   ├── identity.py         # users, scopes, simulated OBO token exchange
    │   ├── validation.py       # schema validation (doubles as the manifest schema)
    │   ├── audit.py            # structured append-only audit log
    │   ├── errors.py           # typed errors → consistent envelope
    │   └── store.py            # in-memory mock data
    ├── salesforce/             # reads.py (get_*) + writes.py (create_*/delete_*)
    ├── jira/                   # writes.py (create_ticket)
    ├── sharepoint/             # reads.py (search_documents — stubbed)
    └── data/                   # accounts / opportunities / tasks / tickets (JSON)
```

## From POC to production (what changes, what doesn't)

**Doesn't change:** the tool contract, the `invoke()` pipeline, read/write separation,
the policy gate, and the audit shape — those are the design.

**Changes (swap implementations behind the same interfaces):**
- `identity.obo_exchange` → a true Entra ID On-Behalf-Of grant for Microsoft
  Graph/SharePoint, and per-connector delegated OAuth token brokers for Salesforce
  and Jira (their own authorization servers) — all acting *as the user*.
- `store` mock lists → real Salesforce REST / Jira REST / Microsoft Graph calls.
- `validation` → pydantic / JSON Schema.
- `audit` sink → Azure Log Analytics → Microsoft Sentinel.
- approval `return` → enqueue to Azure Service Bus, notify the approver named by
  `approval_route` (requesting rep, or a distinct deal-desk approver for binding
  actions), and resume on approval after **re-validating** permissions.
