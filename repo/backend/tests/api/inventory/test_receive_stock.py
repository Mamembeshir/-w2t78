"""
tests/inventory/test_receive_stock.py — Receive stock API tests.

Covers stock receipt, moving average cost calculation, lot tracking, and RBAC.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, Item, ItemLot, TransactionType
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
# 5.3 Receive Stock
# ─────────────────────────────────────────────────────────────────────────────

class ReceiveStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("recv5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "recv5")
        auth(self.client, self.token)
        self.item = make_item("RECV001", CostingMethod.MOVING_AVG)
        self.wh = make_warehouse("RECV_WH")

    def _receive(self, qty, cost, bin_id=None, lot_id=None):
        payload = {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": str(qty),
            "unit_cost": str(cost),
        }
        if bin_id:
            payload["bin_id"] = bin_id
        if lot_id:
            payload["lot_id"] = lot_id
        return self.client.post("/api/inventory/receive/", payload)

    def test_receive_creates_ledger_entry(self):
        resp = self._receive(100, "10.00")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data["ledger_entry"]["transaction_type"], TransactionType.RECEIVE)
        self.assertEqual(Decimal(data["ledger_entry"]["quantity"]), Decimal("100"))

    def test_receive_updates_moving_avg_cost(self):
        self._receive(50, "5.00")
        resp = self._receive(50, "7.00")
        balance = resp.json()["balance"]
        self.assertEqual(Decimal(balance["quantity_on_hand"]), Decimal("100"))
        # Moving average: (50*5 + 50*7) / 100 = 6.00
        self.assertEqual(Decimal(balance["avg_cost"]).quantize(Decimal("0.01")), Decimal("6.00"))

    def test_receive_with_lot(self):
        lot = make_lot(self.item, "L_RECV01")
        resp = self._receive(25, "12.00", lot_id=lot.pk)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["ledger_entry"]["lot"], lot.pk)

    def test_receive_requires_auth(self):
        self.client.credentials()
        resp = self._receive(10, "1.00")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_receive_analyst_forbidden(self):
        analyst = create_user("analyst_recv", Role.PROCUREMENT_ANALYST)
        token = login(self.client, "analyst_recv")
        auth(self.client, token)
        resp = self._receive(10, "1.00")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_receive_zero_quantity_rejected(self):
        resp = self._receive(0, "5.00")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
