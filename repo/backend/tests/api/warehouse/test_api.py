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

    def test_retrieve_warehouse(self):
        wh = Warehouse.objects.create(name="Detail WH", code="DET01", address="1 Main St")
        auth(self.client, self.inv_token)
        resp = self.client.get(f"/api/warehouses/{wh.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["code"], "DET01")
        self.assertIn("name", resp.json())

    def test_full_update_warehouse(self):
        wh = Warehouse.objects.create(name="Old Name", code="PUT01")
        auth(self.client, self.admin_token)
        resp = self.client.put(
            f"/api/warehouses/{wh.pk}/",
            {"name": "New Name", "code": "PUT01", "address": "2 New St"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["name"], "New Name")
        self.assertEqual(resp.json()["address"], "2 New St")

    def test_retrieve_warehouse_unauthenticated(self):
        wh = Warehouse.objects.create(name="No Auth", code="NOAUTH")
        resp = self.client.get(f"/api/warehouses/{wh.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_full_update_warehouse_non_admin_forbidden(self):
        wh = Warehouse.objects.create(name="Protected", code="PROT01")
        auth(self.client, self.inv_token)
        resp = self.client.put(f"/api/warehouses/{wh.pk}/", {"name": "X", "code": "PROT01"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


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

    def test_retrieve_bin(self):
        b = Bin.objects.create(warehouse=self.wh, code="R01", description="Rack R1")
        auth(self.client, self.inv_token)
        resp = self.client.get(f"/api/warehouses/{self.wh.pk}/bins/{b.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["code"], "R01")

    def test_full_update_bin(self):
        b = Bin.objects.create(warehouse=self.wh, code="PUT01")
        auth(self.client, self.admin_token)
        resp = self.client.put(
            f"/api/warehouses/{self.wh.pk}/bins/{b.pk}/",
            {"code": "PUT01", "description": "Updated description"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["description"], "Updated description")

    def test_partial_update_bin(self):
        b = Bin.objects.create(warehouse=self.wh, code="PATCH01", description="Old")
        auth(self.client, self.admin_token)
        resp = self.client.patch(f"/api/warehouses/{self.wh.pk}/bins/{b.pk}/", {"description": "New"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["description"], "New")

    def test_update_bin_non_admin_forbidden(self):
        b = Bin.objects.create(warehouse=self.wh, code="NOPUT")
        auth(self.client, self.inv_token)
        resp = self.client.patch(f"/api/warehouses/{self.wh.pk}/bins/{b.pk}/", {"description": "x"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
