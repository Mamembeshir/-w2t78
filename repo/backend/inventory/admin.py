from django.contrib import admin

from .models import Item, ItemLot, ItemSerial, StockBalance, StockLedger


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "unit_of_measure", "costing_method", "safety_stock_qty", "is_active")
    list_filter = ("costing_method", "is_active")
    search_fields = ("sku", "name")
    ordering = ("sku",)


@admin.register(ItemLot)
class ItemLotAdmin(admin.ModelAdmin):
    list_display = ("__str__", "item", "lot_number", "received_date", "expiry_date")
    list_filter = ("item",)
    search_fields = ("lot_number", "item__sku")


@admin.register(ItemSerial)
class ItemSerialAdmin(admin.ModelAdmin):
    list_display = ("__str__", "item", "serial_number", "status")
    list_filter = ("status", "item")
    search_fields = ("serial_number", "item__sku")


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = ("item", "warehouse", "bin", "transaction_type", "quantity", "unit_cost", "timestamp")
    list_filter = ("transaction_type", "warehouse", "costing_method")
    search_fields = ("item__sku", "reference")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ("item", "warehouse", "bin", "quantity_on_hand", "quantity_reserved", "avg_cost")
    list_filter = ("warehouse",)
    search_fields = ("item__sku",)
