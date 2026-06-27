"""Smoke tests for the connector POC.

Run with the stdlib test runner (no dependencies):  python -m unittest -v
Each test asserts on the consistent Result envelope produced by registry.invoke,
covering allow / deny / validation / approval / block / cross-system paths.
"""
import unittest

import connectors  # noqa: F401  -- registers all tools
from connectors.core.registry import invoke
from connectors.core.identity import get_user
from connectors.core.audit import audit_log


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.alice = get_user("alice")
        self.bob = get_user("bob")
        audit_log.echo = False  # keep test output clean
        audit_log.clear()

    def test_read_allowed(self):
        r = invoke("salesforce.get_account", self.alice, {"account_id": "ACC-001"})
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.data["name"], "Acme Corporation")

    def test_record_level_denial(self):
        r = invoke("salesforce.get_account", self.bob, {"account_id": "ACC-002"})
        self.assertEqual(r.status, "error")
        self.assertEqual(r.error["code"], "unauthorized")

    def test_not_found(self):
        r = invoke("salesforce.get_account", self.alice, {"account_id": "ACC-999"})
        self.assertEqual(r.status, "error")
        self.assertEqual(r.error["code"], "not_found")

    def test_low_risk_write_executes(self):
        r = invoke("salesforce.create_task", self.alice,
                   {"account_id": "ACC-001", "task_description": "Follow up next week"})
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.data["status"], "open")
        self.assertEqual(r.data["created_by"], "alice")

    def test_write_without_scope_denied(self):
        r = invoke("salesforce.create_task", self.bob,
                   {"account_id": "ACC-001", "task_description": "Should be denied"})
        self.assertEqual(r.status, "error")
        self.assertEqual(r.error["code"], "unauthorized")

    def test_validation_error_pattern(self):
        r = invoke("salesforce.get_account", self.alice, {"account_id": "bad"})
        self.assertEqual(r.status, "error")
        self.assertEqual(r.error["code"], "validation_error")

    def test_validation_error_unexpected_field(self):
        r = invoke("salesforce.get_account", self.alice,
                   {"account_id": "ACC-001", "injected": "value"})
        self.assertEqual(r.status, "error")
        self.assertEqual(r.error["code"], "validation_error")

    def test_high_risk_requires_approval(self):
        r = invoke("salesforce.create_opportunity", self.alice,
                   {"account_id": "ACC-001", "name": "Expansion", "amount": 100000})
        self.assertEqual(r.status, "pending_approval")
        self.assertTrue(r.approval_id)

    def test_critical_blocked(self):
        r = invoke("salesforce.delete_opportunity", self.alice, {"opportunity_id": "OPP-1001"})
        self.assertEqual(r.status, "error")
        self.assertEqual(r.error["code"], "policy_blocked")

    def test_cross_system_jira_write(self):
        r = invoke("jira.create_ticket", self.alice, {"summary": "Escalate Acme risk"})
        self.assertEqual(r.status, "ok")
        self.assertTrue(r.data["key"].startswith("SALES-"))

    def test_audit_trail_written(self):
        invoke("salesforce.get_account", self.alice, {"account_id": "ACC-001"})
        events = [rec.event for rec in audit_log.records]
        self.assertIn("decision", events)
        self.assertIn("result", events)


if __name__ == "__main__":
    unittest.main()
