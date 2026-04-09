"""
tests/inventory/test_rbac.py — Inventory RBAC tests.

Verifies role-based access control is enforced correctly on inventory endpoints.
Unauthenticated → 401. Wrong role → 403. Correct role → 2xx.
"""
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


def make_item(sku="SKU001", costing=CostingMethod.MOVING_AVG):
    return Item.objects.create(
        sku=sku, name=f"Item {sku}", unit_of_measure="EA", costing_method=costing
    )


def make_warehouse(code="WH01"):
    return Warehouse.objects.create(name=f"Warehouse {code}", code=code)


# ─────────────────────────────────────────────────────────────────────────────
# RBAC permission tests
# ─────────────────────────────────────────────────────────────────────────────

class InventoryRBACTests(TestCase):
    """
    Verify that role-based access control is enforced correctly on inventory endpoints.
    Unauthenticated → 401.  Wrong role → 403.  Correct role → 2xx.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("rbac_admin", role=Role.ADMIN)
        self.manager = create_user("rbac_manager", role=Role.INVENTORY_MANAGER)
        self.analyst = create_user("rbac_analyst", role=Role.PROCUREMENT_ANALYST)
        self.item = make_item(sku="RBAC001")
        self.wh = make_warehouse("RBAC_WH")

    def _auth(self, user):
        # Use force_authenticate to bypass the login throttle in tests.
        self.client.force_authenticate(user=user)

    # ── Item creation ──────────────────────────────────────────────────────────

    def test_analyst_cannot_create_item(self):
        """PROCUREMENT_ANALYST must not create items (403)."""
        self._auth(self.analyst)
        resp = self.client.post("/api/items/", {
            "sku": "NOAUTH01", "name": "Blocked", "unit_of_measure": "EA",
            "costing_method": "MOVING_AVG",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_create_item(self):
        """INVENTORY_MANAGER may create items (201)."""
        self._auth(self.manager)
        resp = self.client.post("/api/items/", {
            "sku": "AUTH_ITEM01", "name": "Allowed", "unit_of_measure": "EA",
            "costing_method": "MOVING_AVG",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_unauthenticated_cannot_list_items(self):
        """Unauthenticated requests must receive 401."""
        self.client.credentials()
        resp = self.client.get("/api/items/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Stock receive ──────────────────────────────────────────────────────────

    def test_analyst_cannot_receive_stock(self):
        """PROCUREMENT_ANALYST must not post receipts (403)."""
        self._auth(self.analyst)
        resp = self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": "10.0000",
            "unit_cost": "5.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_receive_stock(self):
        """INVENTORY_MANAGER may post receipts (201)."""
        self._auth(self.manager)
        resp = self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": "10.0000",
            "unit_cost": "5.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # ── User management (Admin only) ───────────────────────────────────────────

    def test_manager_cannot_list_users(self):
        """Only ADMINs may access /api/users/ (403 for IM)."""
        self._auth(self.manager)
        resp = self.client.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_users(self):
        """ADMIN may list users (200)."""
        self._auth(self.admin)
        resp = self.client.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_user_cannot_set_superuser(self):
        """API user creation must never produce a superuser."""
        self._auth(self.admin)
        resp = self.client.post("/api/users/", {
            "username": "trysuper", "password": "SafePass1234!",
            "role": "INVENTORY_MANAGER", "is_superuser": True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        from accounts.models import User as U
        u = U.objects.get(username="trysuper")
        self.assertFalse(u.is_superuser)
        self.assertFalse(u.is_staff)

    # ── Issue stock ────────────────────────────────────────────────────────────

    def test_analyst_cannot_issue_stock(self):
        """PROCUREMENT_ANALYST must not post issues (403)."""
        # First put some stock in so the check isn't confused by missing stock
        self._auth(self.manager)
        self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk, "warehouse_id": self.wh.pk,
            "quantity": "50.0000", "unit_cost": "1.00",
        })
        self._auth(self.analyst)
        resp = self.client.post("/api/inventory/issue/", {
            "item_id": self.item.pk, "warehouse_id": self.wh.pk,
            "quantity": "1.0000",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_issue_stock(self):
        """Unauthenticated requests to /api/inventory/issue/ must receive 401."""
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/inventory/issue/", {
            "item_id": self.item.pk, "warehouse_id": self.wh.pk,
            "quantity": "1.0000",
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Transfer stock ─────────────────────────────────────────────────────────

    def test_analyst_cannot_transfer_stock(self):
        """PROCUREMENT_ANALYST must not post transfers (403)."""
        wh2 = make_warehouse("RBAC_WH2")
        self._auth(self.analyst)
        resp = self.client.post("/api/inventory/transfer/", {
            "item_id": self.item.pk,
            "from_warehouse_id": self.wh.pk,
            "to_warehouse_id": wh2.pk,
            "quantity": "1.0000",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_transfer_stock(self):
        """Unauthenticated requests to /api/inventory/transfer/ must receive 401."""
        wh2 = make_warehouse("RBAC_WH3")
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/inventory/transfer/", {
            "item_id": self.item.pk,
            "from_warehouse_id": self.wh.pk,
            "to_warehouse_id": wh2.pk,
            "quantity": "1.0000",
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Stock balances (IsAuthenticated — intentionally broad for single-org) ───

    def test_unauthenticated_cannot_view_balances(self):
        """Unauthenticated requests to /api/inventory/balances/ must receive 401."""
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/inventory/balances/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_analyst_can_view_balances(self):
        """PROCUREMENT_ANALYST may read stock balances — IsAuthenticated is intentional."""
        self._auth(self.analyst)
        resp = self.client.get("/api/inventory/balances/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_manager_can_view_balances(self):
        """INVENTORY_MANAGER may read stock balances."""
        self._auth(self.manager)
        resp = self.client.get("/api/inventory/balances/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
