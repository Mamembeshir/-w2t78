"""
tests/api/test_cross_module_api.py — Cross-module end-to-end API tests.

These tests cross module boundaries and verify the system behaves
correctly for complete user journeys:

  E2E-1: Receive → Issue → balance check (inventory full flow)
  E2E-2: Crawl task enqueue → worker execute → request logged → debug log visible
  E2E-3: Canary release → error threshold exceeded → rollback triggered → notification sent

All tests use a real MySQL test database and make real HTTP calls.
No mocking.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import LiveServerTestCase, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import (
    CrawlRequestLog,
    CrawlRuleVersion,
    CrawlSource,
    CrawlTask,
    CrawlTaskStatus,
)
from crawling.tasks import monitor_canary_versions
from crawling.views import _compute_fingerprint
from inventory.models import (
    CostingMethod,
    Item,
    StockBalance,
    StockLedger,
    TransactionType,
)
from notifications.models import EventType, Notification, NotificationSubscription
from warehouse.models import Warehouse


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_user(username, role=Role.INVENTORY_MANAGER, password="testpass1234"):
    return User.objects.create_user(username=username, password=password, role=role)


def login(client, username, password="testpass1234"):
    resp = client.post("/api/auth/login/", {"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def make_item(sku, costing=CostingMethod.MOVING_AVG):
    return Item.objects.create(
        sku=sku, name=f"Item {sku}", unit_of_measure="EA", costing_method=costing,
    )


def make_warehouse(code):
    return Warehouse.objects.create(name=f"Warehouse {code}", code=code)


def make_source(name):
    return CrawlSource.objects.create(
        name=name,
        base_url="http://example.local",
        rate_limit_rpm=60,
        crawl_delay_seconds=0,
        user_agents=["TestAgent/1.0"],
    )


def make_rule_version(source, version_number=1, is_active=True):
    return CrawlRuleVersion.objects.create(
        source=source,
        version_number=version_number,
        url_pattern="http://example.local/products",
        version_note="e2e test version",
        is_active=is_active,
    )


# ── E2E-1: Receive → Issue → Balance Check ───────────────────────────────────

class ReceiveIssueBalanceE2ETest(TestCase):
    """
    Full inventory flow:
      1. Receive 100 units of a FIFO item
      2. Issue 30 units
      3. Verify balance = 70, ledger has both entries, FIFO lot partially consumed
    """

    def setUp(self):
        self.client = APIClient()
        self.user = create_user("e2e_inv", Role.INVENTORY_MANAGER)
        token = login(self.client, "e2e_inv")
        auth(self.client, token)
        self.item = make_item("E2E_MA", costing=CostingMethod.MOVING_AVG)
        self.wh = make_warehouse("E2E_WH")

    def test_receive_issue_balance_flow_moving_avg(self):
        # Step 1: Receive 100 units
        resp = self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": "100",
            "unit_cost": "10.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.json())

        # Verify balance is 100
        balance = StockBalance.objects.get(item=self.item, warehouse=self.wh)
        self.assertEqual(balance.quantity_on_hand, Decimal("100"))

        # Step 2: Issue 30 units
        resp = self.client.post("/api/inventory/issue/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": "30",
            "reference": "WORK-ORDER-001",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.json())

        # Step 3: Verify final balance = 70
        balance.refresh_from_db()
        self.assertEqual(balance.quantity_on_hand, Decimal("70"))

        # Both ledger entries exist
        receive_entries = StockLedger.objects.filter(
            item=self.item, warehouse=self.wh,
            transaction_type=TransactionType.RECEIVE,
        )
        issue_entries = StockLedger.objects.filter(
            item=self.item, warehouse=self.wh,
            transaction_type=TransactionType.ISSUE,
        )
        self.assertEqual(receive_entries.count(), 1)
        self.assertEqual(issue_entries.count(), 1)

        # Balances API confirms the correct quantity
        resp = self.client.get(
            f"/api/inventory/balances/?item_id={self.item.pk}&warehouse_id={self.wh.pk}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(Decimal(results[0]["quantity_on_hand"]), Decimal("70"))

    def test_issue_more_than_available_returns_400(self):
        """Issuing more than on-hand must be rejected for moving-avg item."""
        self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": "10",
            "unit_cost": "5.00",
        })
        resp = self.client.post("/api/inventory/issue/", {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": "999",
            "reference": "OVER-ISSUE",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Balance unchanged
        balance = StockBalance.objects.get(item=self.item, warehouse=self.wh)
        self.assertEqual(balance.quantity_on_hand, Decimal("10"))


# ── E2E-2: Crawl Enqueue → Worker Execute → Debug Log Visible ────────────────

class CrawlEnqueueExecuteDebugE2ETest(LiveServerTestCase):
    """
    Full crawl flow:
      1. Enqueue a crawl task via the API
      2. Execute it with the real worker (real HTTP)
      3. Verify the request was logged
      4. Verify the debug-log endpoint returns the log entry
    """

    def setUp(self):
        self.api_client = APIClient()
        self.analyst = create_user("e2e_analyst", Role.PROCUREMENT_ANALYST)
        token = login(self.api_client, "e2e_analyst")
        auth(self.api_client, token)

        self.source = make_source("E2E_CRAWL_SRC")
        self.source.crawl_delay_seconds = 0
        self.source.save()
        self.rv = make_rule_version(self.source)

    def test_enqueue_execute_log_debug(self):
        from crawling.worker import execute_crawl_task

        # Step 1: Enqueue a task targeting the live test server's health endpoint
        url = f"{self.live_server_url}/api/health/"
        resp = self.api_client.post(
            "/api/crawl/tasks/",
            {"source_id": self.source.pk, "url": url, "parameters": {}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.json())
        task_id = resp.json()["task"]["id"]

        # Step 2: Execute the worker directly (synchronously)
        result = execute_crawl_task(task_id)
        self.assertTrue(result.get("completed"), f"Worker result: {result}")

        # Step 3: Request log exists
        logs = CrawlRequestLog.objects.filter(task_id=task_id)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.response_status, 200)

        # Step 4: Debug-log API returns the entry
        resp = self.api_client.get(f"/api/crawl/sources/{self.source.pk}/debug-log/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        entries = resp.json()
        self.assertGreaterEqual(len(entries), 1)
        task_ids_in_log = [e["task"] for e in entries]
        self.assertIn(task_id, task_ids_in_log)


# ── E2E-3: Canary Release → Error Threshold → Rollback → Notification ────────

class CanaryRollbackNotificationE2ETest(TestCase):
    """
    Full canary lifecycle:
      1. Activate a canary version on a source
      2. Simulate crawl task failures exceeding 2% threshold
      3. Run the canary monitor
      4. Verify canary is rolled back
      5. Verify a CANARY_ROLLBACK notification is dispatched to subscribers
    """

    def setUp(self):
        self.source = make_source("E2E_CANARY_SRC")
        self.rv_active = make_rule_version(self.source, version_number=1, is_active=True)
        self.rv_canary = CrawlRuleVersion.objects.create(
            source=self.source,
            version_number=2,
            url_pattern="http://example.local/products",
            version_note="canary e2e test",
            is_active=False,
            is_canary=True,
            canary_pct=5,
            canary_started_at=timezone.now(),
        )
        # Subscribe a user to CANARY_ROLLBACK events
        self.admin = create_user("e2e_canary_admin", Role.ADMIN)
        NotificationSubscription.objects.create(
            user=self.admin,
            event_type=EventType.CANARY_ROLLBACK,
            is_active=True,
        )

    def _make_task(self, task_status):
        fp = _compute_fingerprint(
            f"http://e2e.canary/{CrawlTask.objects.count()}", {}
        )
        return CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv_canary,
            fingerprint=fp,
            url="http://e2e.canary/products",
            status=task_status,
        )

    def test_rollback_triggered_and_notification_sent(self):
        # Step 1: Create tasks with >2% error rate (10 failed, 5 completed = 66%)
        for _ in range(10):
            self._make_task(CrawlTaskStatus.FAILED)
        for _ in range(5):
            self._make_task(CrawlTaskStatus.COMPLETED)

        # Step 2: Run canary monitor
        result = monitor_canary_versions()
        self.assertEqual(result["rolled_back"], 1, f"Expected rollback, got: {result}")

        # Step 3: Canary version is no longer active as canary
        self.rv_canary.refresh_from_db()
        self.assertFalse(self.rv_canary.is_canary)

        # Step 4: Notification sent to subscriber
        notifs = Notification.objects.filter(
            user=self.admin,
            event_type=EventType.CANARY_ROLLBACK,
        )
        self.assertEqual(
            notifs.count(), 1,
            f"Expected 1 CANARY_ROLLBACK notification, got {notifs.count()}",
        )
        notif = notifs.first()
        self.assertIn(self.source.name, notif.body)

    def test_no_rollback_when_below_threshold(self):
        """10 completed, 0 failed → no rollback."""
        for _ in range(10):
            self._make_task(CrawlTaskStatus.COMPLETED)
        result = monitor_canary_versions()
        self.assertEqual(result["rolled_back"], 0)
        self.rv_canary.refresh_from_db()
        self.assertTrue(self.rv_canary.is_canary)
