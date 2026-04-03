"""
inventory/tasks.py — Celery beat tasks for inventory automation.

Tasks:
  flag_slow_moving_items   — daily, flags items with no issues in 90 days
  check_safety_stock       — every minute, fires breach notifications after
                             10 consecutive minutes below threshold
"""
from datetime import timedelta

from celery import shared_task
from django.db.models import Sum
from django.utils import timezone


@shared_task(name="inventory.flag_slow_moving_items")
def flag_slow_moving_items():
    """
    Daily task — mark items as slow-moving when no ISSUE transactions
    exist in the last 90 days.  Clears the flag when issues resume.
    """
    from .models import Item, StockLedger, TransactionType

    cutoff = timezone.now() - timedelta(days=90)

    active_skus = set(
        StockLedger.objects.filter(
            transaction_type=TransactionType.ISSUE,
            timestamp__gte=cutoff,
        ).values_list("item_id", flat=True).distinct()
    )

    flagged = 0
    cleared = 0

    for item in Item.objects.filter(deleted_at__isnull=True, is_active=True):
        if item.id not in active_skus:
            if item.slow_moving_flagged_at is None:
                item.slow_moving_flagged_at = timezone.now()
                item.save(update_fields=["slow_moving_flagged_at"])
                flagged += 1
        else:
            if item.slow_moving_flagged_at is not None:
                item.slow_moving_flagged_at = None
                item.save(update_fields=["slow_moving_flagged_at"])
                cleared += 1

    return {"flagged": flagged, "cleared": cleared}


@shared_task(name="inventory.check_safety_stock")
def check_safety_stock():
    """
    Runs every minute.

    For each item+warehouse with a safety_stock_qty configured:
    - If quantity_on_hand < safety_stock_qty: record/update breach state.
      After 10 consecutive minutes below threshold AND alert not yet fired:
      create a Notification for all subscribed users.
    - If quantity_on_hand >= safety_stock_qty: clear any existing breach state.
    """
    from django.db.models import F

    from notifications.models import EventType, Notification, NotificationSubscription
    from .models import Item, SafetyStockBreachState, StockBalance

    now = timezone.now()
    breach_window = timedelta(minutes=10)

    # Fetch all balances where item has a safety stock threshold
    balances = StockBalance.objects.select_related("item", "warehouse").filter(
        item__safety_stock_qty__gt=0,
        item__deleted_at__isnull=True,
    )

    fired = 0
    cleared = 0

    for balance in balances:
        item = balance.item
        warehouse = balance.warehouse
        is_below = balance.quantity_on_hand < item.safety_stock_qty

        if is_below:
            breach, created = SafetyStockBreachState.objects.get_or_create(
                item=item,
                warehouse=warehouse,
                defaults={"breach_started_at": now, "last_checked_at": now},
            )
            if not created:
                breach.last_checked_at = now
                breach.save(update_fields=["last_checked_at"])

            # Fire alert after 10 consecutive minutes, only once per breach
            if not breach.alert_fired and (now - breach.breach_started_at) >= breach_window:
                _fire_safety_stock_notification(item, warehouse, balance)
                breach.alert_fired = True
                breach.save(update_fields=["alert_fired"])
                fired += 1

        else:
            # Quantity recovered — clear breach state
            deleted, _ = SafetyStockBreachState.objects.filter(
                item=item, warehouse=warehouse
            ).delete()
            if deleted:
                cleared += 1

    return {"alerts_fired": fired, "breaches_cleared": cleared}


def _fire_safety_stock_notification(item, warehouse, balance):
    """Create in-app Notification for all subscribers of SAFETY_STOCK_BREACH."""
    from notifications.models import EventType, Notification, NotificationSubscription

    title = f"Safety stock breach: {item.sku}"
    body = (
        f"{item.name} at {warehouse.code} has fallen below safety stock.\n"
        f"On hand: {balance.quantity_on_hand} {item.unit_of_measure} "
        f"(threshold: {item.safety_stock_qty} {item.unit_of_measure})."
    )

    subscriptions = NotificationSubscription.objects.filter(
        event_type=EventType.SAFETY_STOCK_BREACH,
        is_active=True,
    ).select_related("user")

    for sub in subscriptions:
        Notification.objects.create(
            user=sub.user,
            event_type=EventType.SAFETY_STOCK_BREACH,
            title=title,
            body=body,
        )
