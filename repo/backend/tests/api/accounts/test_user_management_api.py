"""
tests/accounts/test_user_management_api.py — User management API tests.

Covers admin CRUD operations on /api/users/ including create, list, retrieve,
update, and reset-password actions.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, password, role=Role.INVENTORY_MANAGER, **kwargs):
    return User.objects.create_user(username=username, password=password, role=role, **kwargs)


def login(client, username, password):
    return client.post("/api/auth/login/", {"username": username, "password": password})


# ─────────────────────────────────────────────────────────────────────────────
# 3.4 — User Management API
# ─────────────────────────────────────────────────────────────────────────────

class UserManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("admin_mgr", "adminmgr123", role=Role.ADMIN)
        resp = login(self.client, "admin_mgr", "adminmgr123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")

    # ── List ─────────────────────────────────────────────────────────────────

    def test_list_users_returns_200(self):
        resp = self.client.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # DRF paginated response includes 'results'
        self.assertIn("results", data)

    def test_list_users_includes_created_user(self):
        create_user("listed_user", "listedpass1")
        resp = self.client.get("/api/users/")
        usernames = [u["username"] for u in resp.json()["results"]]
        self.assertIn("listed_user", usernames)

    # ── Create ───────────────────────────────────────────────────────────────

    def test_create_user_returns_201(self):
        resp = self.client.post("/api/users/", {
            "username": "newuser1",
            "password": "newpassword1",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_user_password_not_in_response(self):
        resp = self.client.post("/api/users/", {
            "username": "newuser2",
            "password": "newpassword2",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertNotIn("password", resp.json())

    def test_create_user_password_hashed_argon2(self):
        self.client.post("/api/users/", {
            "username": "argon2user",
            "password": "argon2password",
            "role": Role.INVENTORY_MANAGER,
        })
        user = User.objects.get(username="argon2user")
        self.assertTrue(
            user.password.startswith("argon2$"),
            f"Expected Argon2 hash, got: {user.password[:30]}",
        )

    def test_create_user_without_password_returns_400(self):
        resp = self.client.post("/api/users/", {
            "username": "nopwduser",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_duplicate_username_returns_400(self):
        create_user("dupeuser", "dupepass123")
        resp = self.client.post("/api/users/", {
            "username": "dupeuser",
            "password": "anotherpass1",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Retrieve ─────────────────────────────────────────────────────────────

    def test_retrieve_user(self):
        user = create_user("retrieveme", "retrieve1pass")
        resp = self.client.get(f"/api/users/{user.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["username"], "retrieveme")

    # ── Update ───────────────────────────────────────────────────────────────

    def test_patch_user_role(self):
        user = create_user("patchme", "patchmepass1", role=Role.INVENTORY_MANAGER)
        resp = self.client.patch(f"/api/users/{user.pk}/", {"role": Role.PROCUREMENT_ANALYST})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["role"], Role.PROCUREMENT_ANALYST)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.PROCUREMENT_ANALYST)

    def test_patch_user_deactivate(self):
        user = create_user("deactivateme", "deactivate1p")
        resp = self.client.patch(f"/api/users/{user.pk}/", {"is_active": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_put_ignores_password_field(self):
        """PUT with a 'password' field should not change the password (update() pops it)."""
        user = create_user("putpasstest", "original1pass", role=Role.INVENTORY_MANAGER)
        original_hash = user.password
        self.client.put(f"/api/users/{user.pk}/", {
            "username": "putpasstest",
            "role": Role.INVENTORY_MANAGER,
            "password": "shouldbeignored1",
        })
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)

    def test_delete_not_allowed(self):
        user = create_user("deleteme", "deleteme1pass")
        resp = self.client.delete(f"/api/users/{user.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ── Reset Password ────────────────────────────────────────────────────────

    def test_reset_password_changes_password(self):
        user = create_user("resetpwd", "oldpassword1")
        resp = self.client.post(f"/api/users/{user.pk}/reset-password/", {"password": "brandnewpass1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("brandnewpass1"))

    def test_reset_password_hashed_argon2(self):
        user = create_user("resetargon", "resetpass123")
        self.client.post(f"/api/users/{user.pk}/reset-password/", {"password": "freshhash1234"})
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("argon2$"))

    def test_reset_password_too_short_returns_400(self):
        user = create_user("shortpwd", "initialpass1")
        resp = self.client.post(f"/api/users/{user.pk}/reset-password/", {"password": "short"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_missing_field_returns_400(self):
        user = create_user("nopwd", "initialpass12")
        resp = self.client.post(f"/api/users/{user.pk}/reset-password/", {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_wrong_key_new_password_returns_400(self):
        """Sending 'new_password' (frontend bug field name) must be rejected — backend expects 'password'."""
        user = create_user("wrongkey", "initialpass13")
        resp = self.client.post(
            f"/api/users/{user.pk}/reset-password/",
            {"new_password": "brandnewpass1"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Password must not have changed
        user.refresh_from_db()
        self.assertTrue(user.check_password("initialpass13"))

    def test_reset_password_correct_key_password_succeeds(self):
        """Sending 'password' (correct field name) must return 200 and update the hash."""
        user = create_user("correctkey", "initialpass14")
        resp = self.client.post(
            f"/api/users/{user.pk}/reset-password/",
            {"password": "updatedpass99"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("updatedpass99"))
