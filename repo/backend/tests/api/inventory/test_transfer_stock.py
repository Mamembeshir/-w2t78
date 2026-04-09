"""
tests/inventory/test_transfer_stock.py — Transfer stock API tests.

Covers inter-warehouse transfers, paired ledger entries, insufficient stock
rejection, and same-location rejection.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, Item, TransactionType
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
# 5.5 Transfer
# ─────────────────────────────────────────────────────────────────────────────

class TransferStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("xfer5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "xfer5")
        auth(self.client, self.token)
        self.item = make_item("XFER001", CostingMethod.MOVING_AVG)
        self.wh_a = make_warehouse("XFER_A")
        self.wh_b = make_warehouse("XFER_B")

    def _receive(self, wh, qty, cost):
        self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk, "warehouse_id": wh.pk,
            "quantity": str(qty), "unit_cost": str(cost),
        })

    def test_transfer_moves_stock_between_warehouses(self):
        self._receive(self.wh_a, 100, "10.00")
        resp = self.client.post("/api/inventory/transfer/", {
            "item_id": self.item.pk,
            "from_warehouse_id": self.wh_a.pk,
            "to_warehouse_id": self.wh_b.pk,
            "quantity": "40",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(Decimal(data["from_balance"]["quantity_on_hand"]), Decimal("60"))
        self.assertEqual(Decimal(data["to_balance"]["quantity_on_hand"]), Decimal("40"))

    def test_transfer_creates_paired_ledger_entries(self):
        self._receive(self.wh_a, 50, "5.00")
        resp = self.client.post("/api/inventory/transfer/", {
            "item_id": self.item.pk,
            "from_warehouse_id": self.wh_a.pk,
            "to_warehouse_id": self.wh_b.pk,
            "quantity": "20",
        })
        self.assertEqual(resp.json()["transfer_out"]["transaction_type"], TransactionType.TRANSFER_OUT)
        self.assertEqual(resp.json()["transfer_in"]["transaction_type"], TransactionType.TRANSFER_IN)

    def test_transfer_insufficient_stock_400(self):
        self._receive(self.wh_a, 10, "5.00")
        resp = self.client.post("/api/inventory/transfer/", {
            "item_id": self.item.pk,
            "from_warehouse_id": self.wh_a.pk,
            "to_warehouse_id": self.wh_b.pk,
            "quantity": "50",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_same_location_rejected(self):
        resp = self.client.post("/api/inventory/transfer/", {
            "item_id": self.item.pk,
            "from_warehouse_id": self.wh_a.pk,
            "to_warehouse_id": self.wh_a.pk,
            "quantity": "10",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
