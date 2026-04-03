"""
warehouse/serializers.py — Warehouse and Bin serializers.
"""
from rest_framework import serializers

from .models import Bin, Warehouse


class BinSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = Bin
        fields = ["id", "warehouse", "warehouse_code", "code", "description", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "warehouse", "created_at", "updated_at"]


class WarehouseSerializer(serializers.ModelSerializer):
    bin_count = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = ["id", "name", "code", "address", "is_active", "bin_count",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_bin_count(self, obj) -> int:
        return obj.bins.filter(deleted_at__isnull=True).count()
