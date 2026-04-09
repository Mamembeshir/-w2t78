"""
tests/inventory/test_stock_balance_api.py — Stock balance API tests.

Covers balance listing, filtering by warehouse, below-safety filter,
and the below_safety_stock flag.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, Item
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
# 5.7 Stock Balance API
# ─────────────────────────────────────────────────────────────────────────────

class StockBalanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("bal5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "bal5")
        auth(self.client, self.token)

    def test_balances_list(self):
        item = make_item("BAL001")
        wh = make_warehouse("BAL_WH")
        self.client.post("/api/inventory/receive/", {
            "item_id": item.pk, "warehouse_id": wh.pk,
            "quantity": "50", "unit_cost": "3.00",
        })
        resp = self.client.get("/api/inventory/balances/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_balances_filter_by_warehouse(self):
        item = make_item("BAL_FILT")
        wh1 = make_warehouse("BFLT1")
        wh2 = make_warehouse("BFLT2")
        self.client.post("/api/inventory/receive/", {
            "item_id": item.pk, "warehouse_id": wh1.pk, "quantity": "10", "unit_cost": "1.00",
        })
        self.client.post("/api/inventory/receive/", {
            "item_id": item.pk, "warehouse_id": wh2.pk, "quantity": "10", "unit_cost": "1.00",
        })
        resp = self.client.get(f"/api/inventory/balances/?warehouse_id={wh1.pk}")
        for row in resp.json()["results"]:
            self.assertEqual(row["warehouse"], wh1.pk)

    def test_balances_below_safety_filter(self):
        item = make_item("SAF001")
        item.safety_stock_qty = Decimal("100")
        item.save()
        wh = make_warehouse("SAF_WH")
        self.client.post("/api/inventory/receive/", {
            "item_id": item.pk, "warehouse_id": wh.pk, "quantity": "10", "unit_cost": "1.00",
        })
        resp = self.client.get("/api/inventory/balances/?below_safety=true")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        skus = [r["item_sku"] for r in resp.json()["results"]]
        self.assertIn("SAF001", skus)

    def test_balance_shows_below_safety_stock_flag(self):
        item = make_item("SAF_FLAG")
        item.safety_stock_qty = Decimal("50")
        item.save()
        wh = make_warehouse("SFFLAG_WH")
        self.client.post("/api/inventory/receive/", {
            "item_id": item.pk, "warehouse_id": wh.pk, "quantity": "10", "unit_cost": "1.00",
        })
        resp = self.client.get("/api/inventory/balances/")
        rows = [r for r in resp.json()["results"] if r["item_sku"] == "SAF_FLAG"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["below_safety_stock"])
