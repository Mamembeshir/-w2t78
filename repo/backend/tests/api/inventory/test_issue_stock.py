"""
tests/inventory/test_issue_stock.py — Issue stock API tests.

Covers moving average and FIFO issue costing, insufficient stock rejection,
and balance updates.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, Item, ItemLot, StockBalance
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


def make_lot(item, lot_number="LOT001"):
    return ItemLot.objects.create(
        item=item, lot_number=lot_number, received_date=timezone.now().date()
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5.4 Issue Stock
# ─────────────────────────────────────────────────────────────────────────────

class IssueStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("issue5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "issue5")
        auth(self.client, self.token)
        self.item_avg = make_item("ISSUE_AVG", CostingMethod.MOVING_AVG)
        self.item_fifo = make_item("ISSUE_FIFO", CostingMethod.FIFO)
        self.wh = make_warehouse("ISSUE_WH")

    def _receive(self, item, qty, cost, lot=None):
        payload = {"item_id": item.pk, "warehouse_id": self.wh.pk, "quantity": str(qty), "unit_cost": str(cost)}
        if lot:
            payload["lot_id"] = lot.pk
        self.client.post("/api/inventory/receive/", payload)

    def _issue(self, item, qty, lot=None, ref="WO-001"):
        payload = {"item_id": item.pk, "warehouse_id": self.wh.pk, "quantity": str(qty), "reference": ref}
        if lot:
            payload["lot_id"] = lot.pk
        return self.client.post("/api/inventory/issue/", payload)

    def test_issue_moving_avg_posts_at_avg_cost(self):
        self._receive(self.item_avg, 100, "10.00")
        resp = self._issue(self.item_avg, 20)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        entries = resp.json()["ledger_entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(Decimal(entries[0]["unit_cost"]).quantize(Decimal("0.01")), Decimal("10.00"))
        self.assertEqual(Decimal(entries[0]["quantity"]), Decimal("-20"))

    def test_issue_fifo_consumes_oldest_lot(self):
        lot_old = ItemLot.objects.create(
            item=self.item_fifo, lot_number="OLD", received_date=datetime.date(2024, 1, 1)
        )
        lot_new = ItemLot.objects.create(
            item=self.item_fifo, lot_number="NEW", received_date=datetime.date(2024, 6, 1)
        )
        self._receive(self.item_fifo, 50, "5.00", lot=lot_old)
        self._receive(self.item_fifo, 50, "8.00", lot=lot_new)
        resp = self._issue(self.item_fifo, 30)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        entries = resp.json()["ledger_entries"]
        # Should consume from oldest lot at $5.00
        self.assertEqual(Decimal(entries[0]["unit_cost"]).quantize(Decimal("0.01")), Decimal("5.00"))

    def test_issue_insufficient_stock_returns_400(self):
        self._receive(self.item_avg, 10, "5.00")
        resp = self._issue(self.item_avg, 20)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()["code"], "insufficient_stock")

    def test_issue_reduces_balance(self):
        self._receive(self.item_avg, 100, "5.00")
        self._issue(self.item_avg, 30)
        balance = StockBalance.objects.get(item=self.item_avg, warehouse=self.wh, bin=None)
        self.assertEqual(balance.quantity_on_hand, Decimal("70"))
