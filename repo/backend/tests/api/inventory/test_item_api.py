"""
tests/inventory/test_item_api.py — Item API tests.

Covers item listing, creation, detail, search, and lots endpoint.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, Item, ItemLot
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
# 5.2 Item API
# ─────────────────────────────────────────────────────────────────────────────

class ItemAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.inv = create_user("inv5", Role.INVENTORY_MANAGER)
        self.analyst = create_user("analyst5", Role.PROCUREMENT_ANALYST)
        self.token = login(self.client, "inv5")
        self.analyst_token = login(self.client, "analyst5")

    def test_list_items(self):
        make_item("LIST01")
        auth(self.client, self.token)
        resp = self.client.get("/api/items/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_create_item_inventory_manager(self):
        auth(self.client, self.token)
        resp = self.client.post("/api/items/", {
            "sku": "NEW001", "name": "New Item", "unit_of_measure": "EA",
            "costing_method": "MOVING_AVG", "safety_stock_qty": "10.0000",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["sku"], "NEW001")

    def test_create_item_analyst_forbidden(self):
        auth(self.client, self.analyst_token)
        resp = self.client.post("/api/items/", {"sku": "NOPE", "name": "Nope", "unit_of_measure": "EA"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_item_detail_includes_totals(self):
        item = make_item("DET001")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/items/{item.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("total_on_hand", data)
        self.assertIn("total_reserved", data)

    def test_search_by_sku(self):
        make_item("SRCH001")
        make_item("SRCH002")
        make_item("OTHER99")
        auth(self.client, self.token)
        resp = self.client.get("/api/items/?q=SRCH")
        skus = [i["sku"] for i in resp.json()["results"]]
        self.assertIn("SRCH001", skus)
        self.assertIn("SRCH002", skus)
        self.assertNotIn("OTHER99", skus)

    def test_item_lots_endpoint(self):
        item = make_item("LOT_ITEM")
        make_lot(item, "L001")
        make_lot(item, "L002")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/items/{item.pk}/lots/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()["results"]), 2)
