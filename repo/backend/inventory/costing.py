"""
inventory/costing.py — FIFO and Moving Average costing engines.

All public functions run inside the caller's database transaction.
They do NOT open their own atomic block — wrap calls in
  with transaction.atomic(): ...
at the view layer.
"""
from decimal import Decimal

from django.db import models as django_models
from django.utils import timezone

from .models import (
    CostingMethod,
    ItemLot,
    StockBalance,
    StockLedger,
    TransactionType,
)


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class InsufficientStockError(Exception):
    """Raised when a requested issue/transfer quantity exceeds available stock."""

    def __init__(self, item_sku: str, requested: Decimal, available: Decimal):
        self.item_sku = item_sku
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for {item_sku}: requested {requested}, available {available}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_balance(item, warehouse, bin_obj):
    """SELECT … FOR UPDATE so concurrent transactions queue behind this one."""
    balance, _ = StockBalance.objects.select_for_update().get_or_create(
        item=item,
        warehouse=warehouse,
        bin=bin_obj,
        defaults={"quantity_on_hand": Decimal("0"), "avg_cost": Decimal("0")},
    )
    return balance


def _fifo_lot_layers(item, warehouse, bin_obj):
    """
    Return a list of (lot, available_qty, receipt_unit_cost) tuples in
    FIFO order (oldest received_date first).

    available_qty = sum of StockLedger.quantity for that lot at this location.
    receipt_unit_cost = unit_cost from the earliest RECEIVE ledger entry for
    that lot at this location (proxy for the lot's landed cost).
    """
    layers = []
    lots = ItemLot.objects.filter(item=item).order_by("received_date", "id")
    for lot in lots:
        agg = StockLedger.objects.filter(
            item=item,
            warehouse=warehouse,
            bin=bin_obj,
            lot=lot,
        ).aggregate(total=django_models.Sum("quantity"))
        available = agg["total"] or Decimal("0")
        if available <= Decimal("0"):
            continue
        # Get the unit_cost from the RECEIVE entry for this lot
        receive_entry = (
            StockLedger.objects.filter(
                item=item,
                warehouse=warehouse,
                bin=bin_obj,
                lot=lot,
                transaction_type=TransactionType.RECEIVE,
            )
            .order_by("timestamp")
            .first()
        )
        lot_cost = receive_entry.unit_cost if receive_entry else Decimal("0")
        layers.append((lot, available, lot_cost))
    return layers


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def post_receive(*, item, warehouse, bin_obj, lot, quantity: Decimal,
                 unit_cost: Decimal, reference: str = "", posted_by):
    """
    Post a stock receipt.

    - Writes one StockLedger row (RECEIVE, positive qty).
    - Updates StockBalance.quantity_on_hand.
    - For MOVING_AVG items: recalculates avg_cost using weighted average.
    - For FIFO items: avg_cost is updated to the latest receipt cost (informational).

    Returns the created StockLedger instance.
    """
    quantity = Decimal(str(quantity))
    unit_cost = Decimal(str(unit_cost))

    balance = _get_or_create_balance(item, warehouse, bin_obj)

    # Update average cost
    if item.costing_method == CostingMethod.MOVING_AVG:
        existing_value = balance.quantity_on_hand * balance.avg_cost
        new_total_qty = balance.quantity_on_hand + quantity
        if new_total_qty > 0:
            balance.avg_cost = (existing_value + quantity * unit_cost) / new_total_qty
        else:
            balance.avg_cost = unit_cost
    else:
        # FIFO — avg_cost holds last receipt cost for reference
        balance.avg_cost = unit_cost

    balance.quantity_on_hand += quantity
    balance.save()

    ledger = StockLedger.objects.create(
        item=item,
        warehouse=warehouse,
        bin=bin_obj,
        lot=lot,
        quantity=quantity,
        unit_cost=unit_cost,
        costing_method=item.costing_method,
        transaction_type=TransactionType.RECEIVE,
        reference=reference,
        posted_by=posted_by,
        timestamp=timezone.now(),
    )
    return ledger


def post_issue(*, item, warehouse, bin_obj, lot, quantity: Decimal,
               reference: str = "", posted_by):
    """
    Post a stock issue.

    - MOVING_AVG: single ledger entry at current avg_cost.
    - FIFO: one ledger entry per lot layer consumed (oldest first).
      If lot is explicitly supplied, consumes from that lot only.

    Returns a list of created StockLedger instances.
    """
    quantity = Decimal(str(quantity))
    balance = _get_or_create_balance(item, warehouse, bin_obj)

    if balance.quantity_on_hand < quantity:
        raise InsufficientStockError(item.sku, quantity, balance.quantity_on_hand)

    now = timezone.now()
    entries = []

    if item.costing_method == CostingMethod.MOVING_AVG:
        unit_cost = balance.avg_cost
        entry = StockLedger.objects.create(
            item=item,
            warehouse=warehouse,
            bin=bin_obj,
            lot=lot,
            quantity=-quantity,
            unit_cost=unit_cost,
            costing_method=item.costing_method,
            transaction_type=TransactionType.ISSUE,
            reference=reference,
            posted_by=posted_by,
            timestamp=now,
        )
        entries.append(entry)

    else:  # FIFO
        if lot is not None:
            # Explicit lot — verify sufficient qty in that lot
            lot_agg = StockLedger.objects.filter(
                item=item, warehouse=warehouse, bin=bin_obj, lot=lot
            ).aggregate(total=django_models.Sum("quantity"))
            lot_available = lot_agg["total"] or Decimal("0")
            if lot_available < quantity:
                raise InsufficientStockError(item.sku, quantity, lot_available)
            receive_entry = (
                StockLedger.objects.filter(
                    item=item, warehouse=warehouse, bin=bin_obj,
                    lot=lot, transaction_type=TransactionType.RECEIVE,
                ).order_by("timestamp").first()
            )
            unit_cost = receive_entry.unit_cost if receive_entry else Decimal("0")
            entry = StockLedger.objects.create(
                item=item,
                warehouse=warehouse,
                bin=bin_obj,
                lot=lot,
                quantity=-quantity,
                unit_cost=unit_cost,
                costing_method=item.costing_method,
                transaction_type=TransactionType.ISSUE,
                reference=reference,
                posted_by=posted_by,
                timestamp=now,
            )
            entries.append(entry)
        else:
            # Auto FIFO — consume oldest layers
            layers = _fifo_lot_layers(item, warehouse, bin_obj)
            remaining = quantity
            for layer_lot, layer_qty, layer_cost in layers:
                if remaining <= 0:
                    break
                take = min(remaining, layer_qty)
                entry = StockLedger.objects.create(
                    item=item,
                    warehouse=warehouse,
                    bin=bin_obj,
                    lot=layer_lot,
                    quantity=-take,
                    unit_cost=layer_cost,
                    costing_method=item.costing_method,
                    transaction_type=TransactionType.ISSUE,
                    reference=reference,
                    posted_by=posted_by,
                    timestamp=now,
                )
                entries.append(entry)
                remaining -= take

    balance.quantity_on_hand -= quantity
    balance.save()
    return entries


def post_transfer(*, item, from_warehouse, from_bin, to_warehouse, to_bin,
                  lot, quantity: Decimal, reference: str = "", posted_by):
    """
    Transfer stock between locations.

    Posts paired TRANSFER_OUT + TRANSFER_IN ledger entries atomically.
    Validates source has sufficient stock before posting either entry.

    Returns (transfer_out_entry, transfer_in_entry).
    """
    quantity = Decimal(str(quantity))

    from_balance = _get_or_create_balance(item, from_warehouse, from_bin)
    if from_balance.quantity_on_hand < quantity:
        raise InsufficientStockError(item.sku, quantity, from_balance.quantity_on_hand)

    to_balance = _get_or_create_balance(item, to_warehouse, to_bin)
    now = timezone.now()

    # Use source location's cost for the transfer
    unit_cost = from_balance.avg_cost

    out_entry = StockLedger.objects.create(
        item=item,
        warehouse=from_warehouse,
        bin=from_bin,
        lot=lot,
        quantity=-quantity,
        unit_cost=unit_cost,
        costing_method=item.costing_method,
        transaction_type=TransactionType.TRANSFER_OUT,
        reference=reference,
        posted_by=posted_by,
        timestamp=now,
    )
    in_entry = StockLedger.objects.create(
        item=item,
        warehouse=to_warehouse,
        bin=to_bin,
        lot=lot,
        quantity=quantity,
        unit_cost=unit_cost,
        costing_method=item.costing_method,
        transaction_type=TransactionType.TRANSFER_IN,
        reference=reference,
        posted_by=posted_by,
        timestamp=now,
    )

    from_balance.quantity_on_hand -= quantity
    from_balance.save()

    # Update to_balance avg_cost if MOVING_AVG
    if item.costing_method == CostingMethod.MOVING_AVG:
        existing_value = to_balance.quantity_on_hand * to_balance.avg_cost
        new_total_qty = to_balance.quantity_on_hand + quantity
        if new_total_qty > 0:
            to_balance.avg_cost = (existing_value + quantity * unit_cost) / new_total_qty
        else:
            to_balance.avg_cost = unit_cost
    to_balance.quantity_on_hand += quantity
    to_balance.save()

    return out_entry, in_entry


def post_cycle_count_adjust(*, item, warehouse, bin_obj, variance_qty: Decimal,
                             unit_cost: Decimal, reference: str = "", posted_by):
    """
    Post a cycle count adjustment ledger entry.

    variance_qty is signed: positive = system was short, negative = system was over.
    Updates StockBalance.quantity_on_hand by variance_qty.

    Returns the created StockLedger instance.
    """
    variance_qty = Decimal(str(variance_qty))
    unit_cost = Decimal(str(unit_cost))

    balance = _get_or_create_balance(item, warehouse, bin_obj)
    now = timezone.now()

    entry = StockLedger.objects.create(
        item=item,
        warehouse=warehouse,
        bin=bin_obj,
        lot=None,
        quantity=variance_qty,
        unit_cost=unit_cost,
        costing_method=item.costing_method,
        transaction_type=TransactionType.CYCLE_COUNT_ADJUST,
        reference=reference,
        posted_by=posted_by,
        timestamp=now,
    )

    balance.quantity_on_hand += variance_qty
    balance.save()

    return entry
