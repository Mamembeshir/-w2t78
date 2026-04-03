"""
inventory/models.py — Item/SKU, lot, serial, and ledger models.

Costing methods (per SKU):
  FIFO         — first-in-first-out cost layers consumed in order
  MOVING_AVG   — weighted moving average cost updated on each receipt

Transaction types for StockLedger:
  RECEIVE            — goods received into a bin
  ISSUE              — goods issued/picked from a bin
  TRANSFER_OUT       — outbound leg of a bin-to-bin transfer
  TRANSFER_IN        — inbound leg of a bin-to-bin transfer
  CYCLE_COUNT_ADJUST — variance posted after a cycle count
"""
from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel, TimeStampedModel
from warehouse.models import Bin, Warehouse


class CostingMethod(models.TextChoices):
    FIFO = "FIFO", "FIFO"
    MOVING_AVG = "MOVING_AVG", "Moving Average"


class TransactionType(models.TextChoices):
    RECEIVE = "RECEIVE", "Receive"
    ISSUE = "ISSUE", "Issue"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"
    TRANSFER_IN = "TRANSFER_IN", "Transfer In"
    CYCLE_COUNT_ADJUST = "CYCLE_COUNT_ADJUST", "Cycle Count Adjustment"


class SerialStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    ISSUED = "ISSUED", "Issued"
    QUARANTINE = "QUARANTINE", "Quarantine"
    SCRAPPED = "SCRAPPED", "Scrapped"


# ─────────────────────────────────────────────────────────────────────────────
# Item / SKU
# ─────────────────────────────────────────────────────────────────────────────

class Item(SoftDeleteModel):
    """
    Master item / SKU record.

    safety_stock_qty  — minimum on-hand quantity before an alert fires.
    costing_method    — FIFO or MOVING_AVG, per-SKU, immutable after first
                        inventory transaction exists.
    """

    sku = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    unit_of_measure = models.CharField(max_length=30, default="EA")
    costing_method = models.CharField(
        max_length=20,
        choices=CostingMethod.choices,
        default=CostingMethod.MOVING_AVG,
    )
    safety_stock_qty = models.DecimalField(
        max_digits=14, decimal_places=4, default=0
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "inventory_item"
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} — {self.name}"


class ItemLot(TimeStampedModel):
    """Lot / batch record for lot-tracked items."""

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="lots")
    lot_number = models.CharField(max_length=100, db_index=True)
    expiry_date = models.DateField(null=True, blank=True)
    received_date = models.DateField()

    class Meta:
        db_table = "inventory_item_lot"
        ordering = ["item", "received_date"]
        unique_together = [("item", "lot_number")]

    def __str__(self):
        return f"{self.item.sku} / Lot {self.lot_number}"


class ItemSerial(TimeStampedModel):
    """Serialised unit record for serial-tracked items."""

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="serials")
    serial_number = models.CharField(max_length=150, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=SerialStatus.choices,
        default=SerialStatus.AVAILABLE,
        db_index=True,
    )

    class Meta:
        db_table = "inventory_item_serial"
        ordering = ["item", "serial_number"]
        unique_together = [("item", "serial_number")]

    def __str__(self):
        return f"{self.item.sku} / SN {self.serial_number}"


# ─────────────────────────────────────────────────────────────────────────────
# Stock Ledger & Balance
# ─────────────────────────────────────────────────────────────────────────────

class StockLedger(TimeStampedModel):
    """
    Immutable transaction log — one row per stock movement.

    quantity is signed: positive for receipts/transfer-in,
    negative for issues/transfer-out.
    """

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="ledger_entries")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="ledger_entries")
    bin = models.ForeignKey(
        Bin, on_delete=models.PROTECT, related_name="ledger_entries", null=True, blank=True
    )
    lot = models.ForeignKey(
        ItemLot, on_delete=models.PROTECT, related_name="ledger_entries", null=True, blank=True
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=6)
    costing_method = models.CharField(max_length=20, choices=CostingMethod.choices)
    transaction_type = models.CharField(
        max_length=30, choices=TransactionType.choices, db_index=True
    )
    reference = models.CharField(max_length=200, blank=True, db_index=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ledger_entries",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "inventory_stock_ledger"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["item", "warehouse", "timestamp"]),
            models.Index(fields=["item", "bin", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} × {self.item.sku} @ {self.timestamp:%Y-%m-%d}"


class StockBalance(TimeStampedModel):
    """
    Denormalised on-hand and reserved quantity per item/warehouse/bin.

    Updated atomically on each transaction.  avg_cost is the current
    moving average cost (for FIFO items this still holds the last receipt cost).
    """

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="balances")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    bin = models.ForeignKey(
        Bin, on_delete=models.PROTECT, related_name="balances", null=True, blank=True
    )
    quantity_on_hand = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    quantity_reserved = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    avg_cost = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    class Meta:
        db_table = "inventory_stock_balance"
        unique_together = [("item", "warehouse", "bin")]
        indexes = [
            models.Index(fields=["item", "warehouse"]),
        ]

    def __str__(self):
        return f"{self.item.sku} @ {self.warehouse.code} — {self.quantity_on_hand} on hand"
