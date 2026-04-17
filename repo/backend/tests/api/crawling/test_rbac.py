"""
tests/crawling/test_rbac.py — Crawling RBAC tests.

Verifies role gates on all crawling endpoints:
unauthenticated → 401, wrong role → 403, correct role → 2xx.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import CrawlRuleVersion, CrawlSource


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.PROCUREMENT_ANALYST):
    return User.objects.create_user(username=username, password="testpass1234", role=role)


def login(client, username):
    resp = client.post("/api/auth/login/", {"username": username, "password": "testpass1234"})
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def make_source(name="TestSource", rate_limit=60):
    return CrawlSource.objects.create(
        name=name,
        base_url="http://example.local",
        rate_limit_rpm=rate_limit,
        crawl_delay_seconds=0,
        user_agents=["TestAgent/1.0"],
    )


def make_rule_version(source, version_number=1, is_active=True, note="Initial version"):
    return CrawlRuleVersion.objects.create(
        source=source,
        version_number=version_number,
        version_note=note,
        url_pattern="http://example.local/products",
        parameters={},
        pagination_config={},
        is_active=is_active,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Crawling RBAC — role gate and unauthenticated 401 matrix
# ─────────────────────────────────────────────────────────────────────────────

class CrawlingRBACTests(TestCase):
    """
    Verify role gates on all crawling endpoints.

    Unauthenticated → 401.  Wrong role → 403.  Correct role → 2xx.

    All tests use real JWT authentication (POST /api/auth/login/) — no
    force_authenticate shortcuts — so the full auth stack is exercised.
    """

    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("crawl_rbac_analyst", Role.PROCUREMENT_ANALYST)
        self.manager = create_user("crawl_rbac_manager", Role.INVENTORY_MANAGER)
        self.admin   = create_user("crawl_rbac_admin",   Role.ADMIN)
        self.source       = make_source("RBAC_SRC")
        self.rule_version = make_rule_version(self.source, is_active=True)
        # Obtain real JWT tokens for each role
        self.analyst_token = login(self.client, "crawl_rbac_analyst")
        self.manager_token = login(self.client, "crawl_rbac_manager")
        self.admin_token   = login(self.client, "crawl_rbac_admin")

    def _as_analyst(self):
        auth(self.client, self.analyst_token)

    def _as_manager(self):
        auth(self.client, self.manager_token)

    def _as_admin(self):
        auth(self.client, self.admin_token)

    def _as_anonymous(self):
        self.client.credentials()  # clear any token

    # ── Sources — list ─────────────────────────────────────────────────────────

    def test_unauthenticated_cannot_list_sources(self):
        """Unauthenticated requests to /api/crawl/sources/ must receive 401."""
        self._as_anonymous()
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_cannot_list_sources(self):
        """INVENTORY_MANAGER must not list crawl sources (403)."""
        self._as_manager()
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_analyst_can_list_sources(self):
        """PROCUREMENT_ANALYST may list crawl sources (200)."""
        self._as_analyst()
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_list_sources(self):
        """ADMIN may list crawl sources (200)."""
        self._as_admin()
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_manager_cannot_retrieve_source_detail(self):
        """INVENTORY_MANAGER must not view crawl source detail (403)."""
        self._as_manager()
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_list_rule_versions(self):
        """INVENTORY_MANAGER must not list rule versions for a source (403)."""
        self._as_manager()
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/rule-versions/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_view_debug_log(self):
        """INVENTORY_MANAGER must not access the debug log endpoint (403)."""
        self._as_manager()
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/debug-log/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_view_quota(self):
        """INVENTORY_MANAGER must not view source quota state (403)."""
        self._as_manager()
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/quota/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Sources — create (ProcurementAnalyst / Admin only) ─────────────────────

    def test_manager_cannot_create_source(self):
        """INVENTORY_MANAGER must not create crawl sources (403)."""
        self._as_manager()
        resp = self.client.post("/api/crawl/sources/", {
            "name": "Blocked", "base_url": "http://block.local",
            "rate_limit_rpm": 30, "crawl_delay_seconds": 1,
            "user_agents": ["UA/1"],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Rule versions — create (ProcurementAnalyst / Admin only) ───────────────

    def test_manager_cannot_create_rule_version(self):
        """INVENTORY_MANAGER must not create rule versions (403)."""
        self._as_manager()
        resp = self.client.post(
            f"/api/crawl/sources/{self.source.pk}/rule-versions/",
            {"version_note": "blocked", "url_pattern": "http://x.local"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create_rule_version(self):
        """Unauthenticated requests to rule-versions must receive 401."""
        self._as_anonymous()
        resp = self.client.post(
            f"/api/crawl/sources/{self.source.pk}/rule-versions/",
            {"version_note": "anon", "url_pattern": "http://x.local"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Tasks — list / enqueue ─────────────────────────────────────────────────

    def test_unauthenticated_cannot_list_tasks(self):
        """Unauthenticated requests to /api/crawl/tasks/ must receive 401."""
        self._as_anonymous()
        resp = self.client.get("/api/crawl/tasks/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_cannot_enqueue_task(self):
        """INVENTORY_MANAGER must not enqueue crawl tasks (403)."""
        self._as_manager()
        resp = self.client.post("/api/crawl/tasks/", {
            "source_id": self.source.pk,
            "url": "http://target.local/page",
            "parameters": {},
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_analyst_can_enqueue_task(self):
        """PROCUREMENT_ANALYST may enqueue a task (201 or 200 if deduplicated)."""
        self._as_analyst()
        resp = self.client.post("/api/crawl/tasks/", {
            "source_id": self.source.pk,
            "url": "http://target.local/rbac-page",
            "parameters": {},
        }, format="json")
        self.assertIn(resp.status_code, (status.HTTP_201_CREATED, status.HTTP_200_OK))
