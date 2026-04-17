"""
tests/inventory/test_item_api.py — Item API tests.

Covers item listing, creation, detail, search, and lots endpoint.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from inventory.models import CostingMethod, Item, ItemLot, ItemSerial, StockLedger, TransactionType
from warehouse.models import Bin, Warehouse


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

    def test_full_update_item(self):
        item = make_item("PUT001")
        auth(self.client, self.token)
        resp = self.client.put(f"/api/items/{item.pk}/", {
            "sku": "PUT001",
            "name": "Updated Item Name",
            "unit_of_measure": "KG",
            "costing_method": "FIFO",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["name"], "Updated Item Name")
        self.assertEqual(resp.json()["unit_of_measure"], "KG")

    def test_partial_update_item(self):
        item = make_item("PATCH001")
        auth(self.client, self.token)
        resp = self.client.patch(f"/api/items/{item.pk}/", {"name": "Patched Name"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["name"], "Patched Name")

    def test_update_item_analyst_forbidden(self):
        item = make_item("FORBID01")
        auth(self.client, self.analyst_token)
        resp = self.client.patch(f"/api/items/{item.pk}/", {"name": "X"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_serials_endpoint_empty(self):
        item = make_item("SER_EMPTY")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/items/{item.pk}/serials/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 0)

    def test_serials_endpoint_with_data(self):
        item = make_item("SER001")
        ItemSerial.objects.create(item=item, serial_number="SN-AAA")
        ItemSerial.objects.create(item=item, serial_number="SN-BBB")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/items/{item.pk}/serials/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 2)
        serial_numbers = [s["serial_number"] for s in resp.json()["results"]]
        self.assertIn("SN-AAA", serial_numbers)
        self.assertIn("SN-BBB", serial_numbers)

    def test_ledger_endpoint_empty(self):
        item = make_item("LEDGER_EMPTY")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/items/{item.pk}/ledger/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 0)

    def test_ledger_endpoint_with_entries(self):
        from decimal import Decimal
        item = make_item("LEDGER01")
        wh = make_warehouse("LEDGERWH")
        StockLedger.objects.create(
            item=item,
            warehouse=wh,
            transaction_type=TransactionType.RECEIVE,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("5.000000"),
            costing_method=CostingMethod.MOVING_AVG,
            posted_by=self.inv,
        )
        auth(self.client, self.token)
        resp = self.client.get(f"/api/items/{item.pk}/ledger/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 1)
        self.assertEqual(resp.json()["results"][0]["transaction_type"], "RECEIVE")
