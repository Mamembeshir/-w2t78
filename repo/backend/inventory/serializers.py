"""
inventory/serializers.py — Item, lot, serial, ledger, balance, and action serializers.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    CycleCountReasonCode,
    CycleCountSession,
    CycleCountStatus,
    Item,
    ItemLot,
    ItemSerial,
    StockBalance,
    StockLedger,
)


# ─────────────────────────────────────────────────────────────────────────────
# Master data
# ─────────────────────────────────────────────────────────────────────────────

class ItemLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemLot
        fields = ["id", "item", "lot_number", "expiry_date", "received_date",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ItemSerialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemSerial
        fields = ["id", "item", "serial_number", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = [
            "id", "sku", "name", "description", "unit_of_measure",
            "costing_method", "safety_stock_qty", "is_active",
            "slow_moving_flagged_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slow_moving_flagged_at", "created_at", "updated_at"]


class ItemDetailSerializer(ItemSerializer):
    """Item detail — includes aggregated stock balance across all locations."""

    total_on_hand = serializers.SerializerMethodField()
    total_reserved = serializers.SerializerMethodField()

    class Meta(ItemSerializer.Meta):
        fields = ItemSerializer.Meta.fields + ["total_on_hand", "total_reserved"]

    def get_total_on_hand(self, obj) -> str:
        from django.db.models import Sum
        result = obj.balances.aggregate(total=Sum("quantity_on_hand"))["total"]
        return str(result or Decimal("0"))

    def get_total_reserved(self, obj) -> str:
        from django.db.models import Sum
        result = obj.balances.aggregate(total=Sum("quantity_reserved"))["total"]
        return str(result or Decimal("0"))


# ─────────────────────────────────────────────────────────────────────────────
# Ledger / Balance
# ─────────────────────────────────────────────────────────────────────────────

class StockLedgerSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True, allow_null=True)
    lot_number = serializers.CharField(source="lot.lot_number", read_only=True, allow_null=True)
    posted_by_username = serializers.CharField(source="posted_by.username", read_only=True, allow_null=True)

    class Meta:
        model = StockLedger
        fields = [
            "id", "item", "item_sku", "warehouse", "warehouse_code",
            "bin", "bin_code", "lot", "lot_number",
            "quantity", "unit_cost", "costing_method", "transaction_type",
            "reference", "posted_by", "posted_by_username", "timestamp",
        ]
        read_only_fields = fields


class StockBalanceSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True, allow_null=True)
    safety_stock_qty = serializers.DecimalField(
        source="item.safety_stock_qty", max_digits=14, decimal_places=4, read_only=True
    )
    below_safety_stock = serializers.SerializerMethodField()

    class Meta:
        model = StockBalance
        fields = [
            "id", "item", "item_sku", "item_name",
            "warehouse", "warehouse_code", "bin", "bin_code",
            "quantity_on_hand", "quantity_reserved", "avg_cost",
            "safety_stock_qty", "below_safety_stock",
            "updated_at",
        ]
        read_only_fields = fields

    def get_below_safety_stock(self, obj) -> bool:
        return obj.quantity_on_hand < obj.item.safety_stock_qty


# ─────────────────────────────────────────────────────────────────────────────
# Action serializers — input validation only (write path)
# ─────────────────────────────────────────────────────────────────────────────

class ReceiveStockSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    bin_id = serializers.IntegerField(required=False, allow_null=True)
    lot_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=6, min_value=Decimal("0"))
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class IssueStockSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    bin_id = serializers.IntegerField(required=False, allow_null=True)
    lot_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    reference = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default="",
        help_text="Work order reference or other document number.",
    )


class TransferSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    from_warehouse_id = serializers.IntegerField()
    from_bin_id = serializers.IntegerField(required=False, allow_null=True)
    to_warehouse_id = serializers.IntegerField()
    to_bin_id = serializers.IntegerField(required=False, allow_null=True)
    lot_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate(self, data):
        if (data["from_warehouse_id"] == data.get("to_warehouse_id")
                and data.get("from_bin_id") == data.get("to_bin_id")):
            raise serializers.ValidationError(
                "Source and destination location must differ."
            )
        return data


class CycleCountStartSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    bin_id = serializers.IntegerField(required=False, allow_null=True)


class CycleCountSubmitSerializer(serializers.Serializer):
    counted_qty = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"))


class CycleCountConfirmSerializer(serializers.Serializer):
    reason_code = serializers.ChoiceField(choices=CycleCountReasonCode.choices)
    supervisor_note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


# ─────────────────────────────────────────────────────────────────────────────
# Cycle Count Session
# ─────────────────────────────────────────────────────────────────────────────

class CycleCountSessionSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True, allow_null=True)
    started_by_username = serializers.CharField(source="started_by.username", read_only=True, allow_null=True)
    confirmed_by_username = serializers.CharField(source="confirmed_by.username", read_only=True, allow_null=True)

    class Meta:
        model = CycleCountSession
        fields = [
            "id", "item", "item_sku", "warehouse", "warehouse_code",
            "bin", "bin_code",
            "expected_qty", "counted_qty", "variance_qty", "variance_value",
            "status", "reason_code", "supervisor_note",
            "started_by", "started_by_username",
            "confirmed_by", "confirmed_by_username",
            "ledger_entry", "created_at", "updated_at",
        ]
        read_only_fields = fields
