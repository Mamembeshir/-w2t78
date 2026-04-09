"""
tests/audit/test_retention.py — Audit log retention/purge tests.

Verifies the purge_old_audit_logs task removes entries older than 365 days
while retaining recent ones.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from audit.models import AuditLog, purge_old_audit_logs


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_log(user=None, action="CREATE", model_name="Item", object_id="1", days_ago=0):
    log = AuditLog._default_manager.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        changes={"field": ["old", "new"]},
    )
    if days_ago:
        # Backdate the timestamp directly via queryset update (bypasses immutability guard)
        AuditLog._default_manager.filter(pk=log.pk).update(
            timestamp=timezone.now() - timedelta(days=days_ago)
        )
    return log


# ─────────────────────────────────────────────────────────────────────────────
# A.6  purge_old_audit_logs task
# ─────────────────────────────────────────────────────────────────────────────

class AuditPurgeTaskTests(TestCase):
    def test_purges_entries_older_than_365_days(self):
        """Entries older than 365 days must be deleted by the purge task."""
        old_log = make_log(days_ago=366)
        recent_log = make_log(days_ago=10)

        result = purge_old_audit_logs()

        self.assertGreaterEqual(result["deleted"], 1)
        # Old entry gone
        self.assertFalse(AuditLog._default_manager.filter(pk=old_log.pk).exists())
        # Recent entry retained
        self.assertTrue(AuditLog._default_manager.filter(pk=recent_log.pk).exists())

    def test_purge_returns_deleted_count(self):
        """Task must return a dict with deleted count and cutoff."""
        make_log(days_ago=400)
        make_log(days_ago=400)
        result = purge_old_audit_logs()
        self.assertIn("deleted", result)
        self.assertIn("cutoff", result)
        self.assertGreaterEqual(result["deleted"], 2)

    def test_purge_does_not_delete_recent_entries(self):
        """Entries within 365 days must be preserved."""
        make_log(days_ago=364)
        make_log(days_ago=0)
        before = AuditLog._default_manager.filter(
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        purge_old_audit_logs()
        after = AuditLog._default_manager.filter(
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        self.assertEqual(before, after)

    def test_purge_no_op_when_nothing_old(self):
        """Task returns deleted=0 when no old entries exist."""
        make_log(days_ago=30)
        result = purge_old_audit_logs()
        self.assertEqual(result["deleted"], 0)
