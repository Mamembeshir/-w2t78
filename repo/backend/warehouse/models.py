"""
warehouse/models.py — Warehouse and Bin models.
"""
from django.db import models

from core.models import SoftDeleteModel, TimeStampedModel


class Warehouse(SoftDeleteModel):
    """Physical warehouse location."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, unique=True, db_index=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "warehouse_warehouse"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Bin(SoftDeleteModel):
    """Storage bin/location within a warehouse."""

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="bins",
    )
    code = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "warehouse_bin"
        ordering = ["warehouse", "code"]
        unique_together = [("warehouse", "code")]

    def __str__(self):
        return f"{self.warehouse.code}/{self.code}"
