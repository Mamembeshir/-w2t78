"""
tests/inventory/test_safety_stock.py — Safety stock task tests.

Covers the check_safety_stock Celery task with 10-minute flap prevention:
no alert before 10 minutes, alert fires after 10 minutes, fires only once,
and clears when stock recovers.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import (
    CostingMethod,
    Item,
    SafetyStockBreachState,
    StockBalance,
)
from notifications.models import EventType, Notification, NotificationSubscription
from warehouse.models import Warehouse


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.INVENTORY_MANAGER):
    return User.objects.create_user(username=username, password="testpass1234", role=role)


def make_item(sku="SKU001", costing=CostingMethod.MOVING_AVG):
    return Item.objects.create(
        sku=sku, name=f"Item {sku}", unit_of_measure="EA", costing_method=costing
    )


def make_warehouse(code="WH01"):
    return Warehouse.objects.create(name=f"Warehouse {code}", code=code)


# ─────────────────────────────────────────────────────────────────────────────
# 8.3 Safety Stock Breach Task (10-minute flap prevention)
# ─────────────────────────────────────────────────────────────────────────────

class SafetyStockTaskTests(TestCase):
    """Tests for the check_safety_stock Celery task (Phase 8.3)."""

    def setUp(self):
        self.wh = make_warehouse("SST_WH")
        self.item = make_item("SST001")
        self.item.safety_stock_qty = Decimal("100")
        self.item.save()
        # Create a balance below the threshold
        StockBalance.objects.create(
            item=self.item,
            warehouse=self.wh,
            quantity_on_hand=Decimal("10"),
        )
        # Subscribe a user to safety stock breach events
        self.user = create_user("sst_sub", Role.INVENTORY_MANAGER)
        NotificationSubscription.objects.create(
            user=self.user,
            event_type=EventType.SAFETY_STOCK_BREACH,
            is_active=True,
        )

    def _run_check(self):
        from inventory.tasks import check_safety_stock
        return check_safety_stock()

    def test_no_alert_before_10_minutes(self):
        """Breach started 5 minutes ago — no notification yet."""
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=5),
            last_checked_at=timezone.now() - timedelta(minutes=5),
        )
        result = self._run_check()
        self.assertEqual(result["alerts_fired"], 0)
        breach = SafetyStockBreachState.objects.get(item=self.item, warehouse=self.wh)
        self.assertFalse(breach.alert_fired)

    def test_fires_alert_after_10_minutes(self):
        """Breach started 11 minutes ago — notification must be created."""
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=11),
            last_checked_at=timezone.now() - timedelta(minutes=1),
        )
        result = self._run_check()
        self.assertEqual(result["alerts_fired"], 1)
        breach = SafetyStockBreachState.objects.get(item=self.item, warehouse=self.wh)
        self.assertTrue(breach.alert_fired)
        # Notification created for subscriber
        notif_count = Notification.objects.filter(
            user=self.user,
            event_type=EventType.SAFETY_STOCK_BREACH,
        ).count()
        self.assertEqual(notif_count, 1)

    def test_alert_fires_only_once(self):
        """alert_fired=True means second check_safety_stock call fires nothing."""
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=11),
            last_checked_at=timezone.now(),
            alert_fired=True,
        )
        result = self._run_check()
        self.assertEqual(result["alerts_fired"], 0)

    def test_clears_breach_when_stock_recovered(self):
        """Balance back above threshold — breach state deleted."""
        self.item.safety_stock_qty = Decimal("5")  # now balance (10) is above threshold
        self.item.save()
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=2),
            last_checked_at=timezone.now(),
        )
        result = self._run_check()
        self.assertEqual(result["breaches_cleared"], 1)
        self.assertFalse(
            SafetyStockBreachState.objects.filter(item=self.item, warehouse=self.wh).exists()
        )
