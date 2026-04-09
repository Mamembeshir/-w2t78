"""
tests/inventory/test_cycle_count.py — Cycle count API tests.

Covers session creation, variance confirmation thresholds, ledger postings,
and RBAC guards.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, CycleCountStatus, Item, ItemLot, StockBalance
from warehouse.models import Warehouse


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.INVENTORY_MANAGER):
    return User.objects.create_user(username=username, password="testpass1234", role=role)


def login(client, username):
    resp = client.post("/api/auth/login/", {"username": username, "password": "testpass1234"})
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def make_item(sku="SKU001", costing=CostingMethod.MOVING_AVG):
    return Item.objects.create(
        sku=sku, name=f"Item {sku}", unit_of_measure="EA", costing_method=costing
    )


def make_warehouse(code="WH01"):
    return Warehouse.objects.create(name=f"Warehouse {code}", code=code)


# ─────────────────────────────────────────────────────────────────────────────
# 5.6 Cycle Count
# ─────────────────────────────────────────────────────────────────────────────

class CycleCountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("cc5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "cc5")
        auth(self.client, self.token)
        self.item = make_item("CC001", CostingMethod.MOVING_AVG)
        self.wh = make_warehouse("CC_WH")
        # Receive initial stock at $5/unit
        self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk, "warehouse_id": self.wh.pk,
            "quantity": "100", "unit_cost": "5.00",
        })

    def _start(self, item=None, wh=None):
        return self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": (item or self.item).pk,
            "warehouse_id": (wh or self.wh).pk,
        })

    def test_start_creates_session_with_expected_qty(self):
        resp = self._start()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data["status"], CycleCountStatus.OPEN)
        self.assertEqual(Decimal(data["expected_qty"]), Decimal("100"))

    def test_submit_small_variance_auto_confirms(self):
        start = self._start().json()
        # variance: -1 unit @ $5 = $5 < $500 — auto confirm
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "99"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.json()["variance_confirmation_required"])
        self.assertEqual(resp.json()["session"]["status"], CycleCountStatus.CONFIRMED)
        # Balance should be updated to 99
        balance = StockBalance.objects.get(item=self.item, warehouse=self.wh, bin=None)
        self.assertEqual(balance.quantity_on_hand, Decimal("99"))

    def test_submit_large_variance_requires_confirmation(self):
        """100 units @ $10 = $1000 variance exceeds $500 threshold."""
        item_hi = make_item("CC_HI", CostingMethod.MOVING_AVG)
        self.client.post("/api/inventory/receive/", {
            "item_id": item_hi.pk, "warehouse_id": self.wh.pk,
            "quantity": "100", "unit_cost": "10.00",
        })
        start = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": item_hi.pk, "warehouse_id": self.wh.pk,
        }).json()
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "0"},  # variance: 100 @ $10 = $1000 > $500
        )
        self.assertTrue(resp.json()["variance_confirmation_required"])
        self.assertEqual(resp.json()["session"]["status"], CycleCountStatus.PENDING_CONFIRM)

    def test_confirm_posts_ledger_and_adjusts_balance(self):
        item_c = make_item("CC_CONF2", CostingMethod.MOVING_AVG)
        self.client.post("/api/inventory/receive/", {
            "item_id": item_c.pk, "warehouse_id": self.wh.pk,
            "quantity": "100", "unit_cost": "20.00",
        })
        start = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": item_c.pk, "warehouse_id": self.wh.pk,
        }).json()
        # 100 * 20 = 2000 > 500 → requires confirmation
        self.client.post(f"/api/inventory/cycle-count/{start['id']}/submit/", {"counted_qty": "0"})
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/confirm/",
            {"reason_code": "DAMAGE", "supervisor_note": "Water damage"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["status"], CycleCountStatus.CONFIRMED)
        balance = StockBalance.objects.get(item=item_c, warehouse=self.wh, bin=None)
        self.assertEqual(balance.quantity_on_hand, Decimal("0"))

    def test_variance_exactly_at_threshold_does_not_require_confirmation(self):
        """Variance of exactly $500.00 is NOT > threshold — should auto-confirm."""
        # 100 units on hand @ $5/unit → avg_cost = $5
        # counted_qty = 0 → variance_qty = -100, variance_value = 100 * $5 = $500
        # $500 is NOT > $500 → auto-confirmed
        start = self._start().json()
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "0"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.json()["variance_confirmation_required"])
        self.assertEqual(resp.json()["session"]["status"], CycleCountStatus.CONFIRMED)

    def test_variance_just_above_threshold_requires_confirmation(self):
        """101 units @ $5 = $505 variance — must require confirmation."""
        item_v = make_item("CC_BORDER", CostingMethod.MOVING_AVG)
        self.client.post("/api/inventory/receive/", {
            "item_id": item_v.pk, "warehouse_id": self.wh.pk,
            "quantity": "101", "unit_cost": "5.00",
        })
        start = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": item_v.pk, "warehouse_id": self.wh.pk,
        }).json()
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "0"},  # 101 * $5 = $505 > $500
        )
        self.assertTrue(resp.json()["variance_confirmation_required"])
        self.assertEqual(resp.json()["session"]["status"], CycleCountStatus.PENDING_CONFIRM)

    def test_cannot_submit_already_confirmed_session(self):
        """Submitting to a CONFIRMED session should return 404."""
        start = self._start().json()
        self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "99"},
        )
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "50"},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_analyst_cannot_start_cycle_count(self):
        """PROCUREMENT_ANALYST must not start cycle counts (403)."""
        analyst = create_user("cc_analyst", Role.PROCUREMENT_ANALYST)
        self.client.force_authenticate(user=analyst)
        resp = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_start_cycle_count(self):
        """Unauthenticated requests must receive 401."""
        self.client.credentials()
        resp = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
