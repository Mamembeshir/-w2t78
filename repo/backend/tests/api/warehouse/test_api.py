"""
tests/warehouse/test_api.py — Warehouse and Bin API tests.

Covers listing, creating, updating warehouses and bins, authentication guards,
role-based access control, and duplicate code rejection.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from warehouse.models import Bin, Warehouse


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.ADMIN):
    u = User.objects.create_user(username=username, password="testpass1234", role=role)
    return u


def login(client, username):
    resp = client.post("/api/auth/login/", {"username": username, "password": "testpass1234"})
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ─────────────────────────────────────────────────────────────────────────────
# Warehouse API
# ─────────────────────────────────────────────────────────────────────────────

class WarehouseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("wh_admin", Role.ADMIN)
        self.inv_mgr = create_user("wh_inv", Role.INVENTORY_MANAGER)
        self.admin_token = login(self.client, "wh_admin")
        self.inv_token = login(self.client, "wh_inv")

    def test_list_warehouses_authenticated(self):
        Warehouse.objects.create(name="Main", code="WH01")
        auth(self.client, self.inv_token)
        resp = self.client.get("/api/warehouses/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_list_warehouses_unauthenticated(self):
        resp = self.client.get("/api/warehouses/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_warehouse_admin(self):
        auth(self.client, self.admin_token)
        resp = self.client.post("/api/warehouses/", {"name": "East Wing", "code": "EW01", "address": "Block A"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["code"], "EW01")

    def test_create_warehouse_non_admin_forbidden(self):
        auth(self.client, self.inv_token)
        resp = self.client.post("/api/warehouses/", {"name": "X", "code": "XX1"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_warehouse_admin(self):
        wh = Warehouse.objects.create(name="Old", code="UPD01")
        auth(self.client, self.admin_token)
        resp = self.client.patch(f"/api/warehouses/{wh.pk}/", {"name": "New Name"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["name"], "New Name")

    def test_duplicate_code_rejected(self):
        Warehouse.objects.create(name="A", code="DUP01")
        auth(self.client, self.admin_token)
        resp = self.client.post("/api/warehouses/", {"name": "B", "code": "DUP01"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# Bin API
# ─────────────────────────────────────────────────────────────────────────────

class BinAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("bin_admin", Role.ADMIN)
        self.inv_mgr = create_user("bin_inv", Role.INVENTORY_MANAGER)
        self.admin_token = login(self.client, "bin_admin")
        self.inv_token = login(self.client, "bin_inv")
        self.wh = Warehouse.objects.create(name="BinWH", code="BINWH")

    def test_list_bins_authenticated(self):
        Bin.objects.create(warehouse=self.wh, code="A01")
        auth(self.client, self.inv_token)
        resp = self.client.get(f"/api/warehouses/{self.wh.pk}/bins/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_create_bin_admin(self):
        auth(self.client, self.admin_token)
        resp = self.client.post(f"/api/warehouses/{self.wh.pk}/bins/", {"code": "B01", "description": "Shelf B1"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["code"], "B01")
        self.assertEqual(resp.json()["warehouse"], self.wh.pk)

    def test_create_bin_non_admin_forbidden(self):
        auth(self.client, self.inv_token)
        resp = self.client.post(f"/api/warehouses/{self.wh.pk}/bins/", {"code": "B02"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
