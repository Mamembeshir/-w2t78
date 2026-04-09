"""
tests/audit/test_immutability.py — Audit log immutability tests.

Verifies that AuditLog records cannot be modified or deleted after creation.
"""
from django.test import TestCase

from audit.models import AuditLog


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_log(user=None, action="CREATE", model_name="Item", object_id="1", days_ago=0):
    from datetime import timedelta
    from django.utils import timezone
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
# A.3  AuditLog immutability
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogImmutabilityTests(TestCase):
    def test_save_existing_raises(self):
        """Calling .save() on an existing AuditLog must raise NotImplementedError."""
        log = make_log()
        log.action = "DELETE"
        with self.assertRaises(NotImplementedError):
            log.save()

    def test_delete_instance_raises(self):
        """Calling .delete() on an AuditLog instance must raise NotImplementedError."""
        log = make_log()
        with self.assertRaises(NotImplementedError):
            log.delete()

    def test_create_succeeds(self):
        """Creating a new AuditLog entry must work normally."""
        log = make_log(action="UPDATE", model_name="Warehouse", object_id="99")
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.action, "UPDATE")
