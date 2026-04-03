"""
inventory/tests.py — Real-database integration tests for Phase 5.2–5.8.

Run:
  docker compose exec backend python manage.py test inventory --verbosity=2 --keepdb
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from warehouse.models import Bin, Warehouse

from .models import (
    CostingMethod,
    CycleCountStatus,
    Item,
    ItemLot,
    SafetyStockBreachState,
    StockBalance,
    StockLedger,
    TransactionType,
)


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
    from django.utils import timezone
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


# ─────────────────────────────────────────────────────────────────────────────
# 5.3 Receive Stock
# ─────────────────────────────────────────────────────────────────────────────

class ReceiveStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("recv5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "recv5")
        auth(self.client, self.token)
        self.item = make_item("RECV001", CostingMethod.MOVING_AVG)
        self.wh = make_warehouse("RECV_WH")

    def _receive(self, qty, cost, bin_id=None, lot_id=None):
        payload = {
            "item_id": self.item.pk,
            "warehouse_id": self.wh.pk,
            "quantity": str(qty),
            "unit_cost": str(cost),
        }
        if bin_id:
            payload["bin_id"] = bin_id
        if lot_id:
            payload["lot_id"] = lot_id
        return self.client.post("/api/inventory/receive/", payload)

    def test_receive_creates_ledger_entry(self):
        resp = self._receive(100, "10.00")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data["ledger_entry"]["transaction_type"], TransactionType.RECEIVE)
        self.assertEqual(Decimal(data["ledger_entry"]["quantity"]), Decimal("100"))

    def test_receive_updates_moving_avg_cost(self):
        self._receive(50, "5.00")
        resp = self._receive(50, "7.00")
        balance = resp.json()["balance"]
        self.assertEqual(Decimal(balance["quantity_on_hand"]), Decimal("100"))
        # Moving average: (50*5 + 50*7) / 100 = 6.00
        self.assertEqual(Decimal(balance["avg_cost"]).quantize(Decimal("0.01")), Decimal("6.00"))

    def test_receive_with_lot(self):
        lot = make_lot(self.item, "L_RECV01")
        resp = self._receive(25, "12.00", lot_id=lot.pk)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["ledger_entry"]["lot"], lot.pk)

    def test_receive_requires_auth(self):
        self.client.credentials()
        resp = self._receive(10, "1.00")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_receive_analyst_forbidden(self):
        analyst = create_user("analyst_recv", Role.PROCUREMENT_ANALYST)
        token = login(self.client, "analyst_recv")
        auth(self.client, token)
        resp = self._receive(10, "1.00")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_receive_zero_quantity_rejected(self):
        resp = self._receive(0, "5.00")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# 5.4 Issue Stock
# ─────────────────────────────────────────────────────────────────────────────

class IssueStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("issue5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "issue5")
        auth(self.client, self.token)
        self.item_avg = make_item("ISSUE_AVG", CostingMethod.MOVING_AVG)
        self.item_fifo = make_item("ISSUE_FIFO", CostingMethod.FIFO)
        self.wh = make_warehouse("ISSUE_WH")

    def _receive(self, item, qty, cost, lot=None):
        payload = {"item_id": item.pk, "warehouse_id": self.wh.pk, "quantity": str(qty), "unit_cost": str(cost)}
        if lot:
            payload["lot_id"] = lot.pk
        self.client.post("/api/inventory/receive/", payload)

    def _issue(self, item, qty, lot=None, ref="WO-001"):
        payload = {"item_id": item.pk, "warehouse_id": self.wh.pk, "quantity": str(qty), "reference": ref}
        if lot:
            payload["lot_id"] = lot.pk
        return self.client.post("/api/inventory/issue/", payload)

    def test_issue_moving_avg_posts_at_avg_cost(self):
        self._receive(self.item_avg, 100, "10.00")
        resp = self._issue(self.item_avg, 20)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        entries = resp.json()["ledger_entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(Decimal(entries[0]["unit_cost"]).quantize(Decimal("0.01")), Decimal("10.00"))
        self.assertEqual(Decimal(entries[0]["quantity"]), Decimal("-20"))

    def test_issue_fifo_consumes_oldest_lot(self):
        import datetime
        lot_old = ItemLot.objects.create(
            item=self.item_fifo, lot_number="OLD", received_date=datetime.date(2024, 1, 1)
        )
        lot_new = ItemLot.objects.create(
            item=self.item_fifo, lot_number="NEW", received_date=datetime.date(2024, 6, 1)
        )
        self._receive(self.item_fifo, 50, "5.00", lot=lot_old)
        self._receive(self.item_fifo, 50, "8.00", lot=lot_new)
        resp = self._issue(self.item_fifo, 30)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        entries = resp.json()["ledger_entries"]
        # Should consume from oldest lot at $5.00
        self.assertEqual(Decimal(entries[0]["unit_cost"]).quantize(Decimal("0.01")), Decimal("5.00"))

    def test_issue_insufficient_stock_returns_400(self):
        self._receive(self.item_avg, 10, "5.00")
        resp = self._issue(self.item_avg, 20)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()["code"], "insufficient_stock")

    def test_issue_reduces_balance(self):
        self._receive(self.item_avg, 100, "5.00")
        self._issue(self.item_avg, 30)
        balance = StockBalance.objects.get(item=self.item_avg, warehouse=self.wh, bin=None)
        self.assertEqual(balance.quantity_on_hand, Decimal("70"))


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


# ─────────────────────────────────────────────────────────────────────────────
# 5.6 Cycle Count
# ─────────────────────────────────────────────────────────────────────────────

class CycleCountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("cc5", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "cc5")
        auth(self.client, self.token)
        self.item = make_item("CC001", CostingMethod.MOVING_AVG)
        self.wh = make_warehouse("CC_WH")
        # Receive initial stock at $5/unit
        self.client.post("/api/inventory/receive/", {
            "item_id": self.item.pk, "warehouse_id": self.wh.pk,
            "quantity": "100", "unit_cost": "5.00",
        })

    def _start(self, item=None, wh=None):
        return self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": (item or self.item).pk,
            "warehouse_id": (wh or self.wh).pk,
        })

    def test_start_creates_session_with_expected_qty(self):
        resp = self._start()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data["status"], CycleCountStatus.OPEN)
        self.assertEqual(Decimal(data["expected_qty"]), Decimal("100"))

    def test_submit_small_variance_auto_confirms(self):
        start = self._start().json()
        # variance: -1 unit @ $5 = $5 < $500 — auto confirm
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "99"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.json()["variance_confirmation_required"])
        self.assertEqual(resp.json()["session"]["status"], CycleCountStatus.CONFIRMED)
        # Balance should be updated to 99
        balance = StockBalance.objects.get(item=self.item, warehouse=self.wh, bin=None)
        self.assertEqual(balance.quantity_on_hand, Decimal("99"))

    def test_submit_large_variance_requires_confirmation(self):
        """100 units @ $10 = $1000 variance exceeds $500 threshold."""
        item_hi = make_item("CC_HI", CostingMethod.MOVING_AVG)
        self.client.post("/api/inventory/receive/", {
            "item_id": item_hi.pk, "warehouse_id": self.wh.pk,
            "quantity": "100", "unit_cost": "10.00",
        })
        start = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": item_hi.pk, "warehouse_id": self.wh.pk,
        }).json()
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/submit/",
            {"counted_qty": "0"},  # variance: 100 @ $10 = $1000 > $500
        )
        self.assertTrue(resp.json()["variance_confirmation_required"])
        self.assertEqual(resp.json()["session"]["status"], CycleCountStatus.PENDING_CONFIRM)

    def test_confirm_posts_ledger_and_adjusts_balance(self):
        item_c = make_item("CC_CONF2", CostingMethod.MOVING_AVG)
        self.client.post("/api/inventory/receive/", {
            "item_id": item_c.pk, "warehouse_id": self.wh.pk,
            "quantity": "100", "unit_cost": "20.00",
        })
        start = self.client.post("/api/inventory/cycle-count/start/", {
            "item_id": item_c.pk, "warehouse_id": self.wh.pk,
        }).json()
        # 100 * 20 = 2000 > 500 → requires confirmation
        self.client.post(f"/api/inventory/cycle-count/{start['id']}/submit/", {"counted_qty": "0"})
        resp = self.client.post(
            f"/api/inventory/cycle-count/{start['id']}/confirm/",
            {"reason_code": "DAMAGE", "supervisor_note": "Water damage"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["status"], CycleCountStatus.CONFIRMED)
        balance = StockBalance.objects.get(item=item_c, warehouse=self.wh, bin=None)
        self.assertEqual(balance.quantity_on_hand, Decimal("0"))


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


# ─────────────────────────────────────────────────────────────────────────────
# 8.3 Safety Stock Breach Task (10-minute flap prevention)
# ─────────────────────────────────────────────────────────────────────────────

class SafetyStockTaskTests(TestCase):
    """Tests for the check_safety_stock Celery task (Phase 8.3)."""

    def setUp(self):
        from notifications.models import NotificationSubscription, EventType
        self.wh = make_warehouse("SST_WH")
        self.item = make_item("SST001")
        self.item.safety_stock_qty = Decimal("100")
        self.item.save()
        # Create a balance below the threshold
        StockBalance.objects.create(
            item=self.item,
            warehouse=self.wh,
            quantity_on_hand=Decimal("10"),
        )
        # Subscribe a user to safety stock breach events
        self.user = create_user("sst_sub", Role.INVENTORY_MANAGER)
        NotificationSubscription.objects.create(
            user=self.user,
            event_type=EventType.SAFETY_STOCK_BREACH,
            is_active=True,
        )

    def _run_check(self):
        from .tasks import check_safety_stock
        return check_safety_stock()

    def test_no_alert_before_10_minutes(self):
        """Breach started 5 minutes ago — no notification yet."""
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=5),
            last_checked_at=timezone.now() - timedelta(minutes=5),
        )
        result = self._run_check()
        self.assertEqual(result["alerts_fired"], 0)
        breach = SafetyStockBreachState.objects.get(item=self.item, warehouse=self.wh)
        self.assertFalse(breach.alert_fired)

    def test_fires_alert_after_10_minutes(self):
        """Breach started 11 minutes ago — notification must be created."""
        from notifications.models import Notification, EventType
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=11),
            last_checked_at=timezone.now() - timedelta(minutes=1),
        )
        result = self._run_check()
        self.assertEqual(result["alerts_fired"], 1)
        breach = SafetyStockBreachState.objects.get(item=self.item, warehouse=self.wh)
        self.assertTrue(breach.alert_fired)
        # Notification created for subscriber
        notif_count = Notification.objects.filter(
            user=self.user,
            event_type=EventType.SAFETY_STOCK_BREACH,
        ).count()
        self.assertEqual(notif_count, 1)

    def test_alert_fires_only_once(self):
        """alert_fired=True means second check_safety_stock call fires nothing."""
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=11),
            last_checked_at=timezone.now(),
            alert_fired=True,
        )
        result = self._run_check()
        self.assertEqual(result["alerts_fired"], 0)

    def test_clears_breach_when_stock_recovered(self):
        """Balance back above threshold — breach state deleted."""
        self.item.safety_stock_qty = Decimal("5")  # now balance (10) is above threshold
        self.item.save()
        SafetyStockBreachState.objects.create(
            item=self.item,
            warehouse=self.wh,
            breach_started_at=timezone.now() - timedelta(minutes=2),
            last_checked_at=timezone.now(),
        )
        result = self._run_check()
        self.assertEqual(result["breaches_cleared"], 1)
        self.assertFalse(
            SafetyStockBreachState.objects.filter(item=self.item, warehouse=self.wh).exists()
        )
