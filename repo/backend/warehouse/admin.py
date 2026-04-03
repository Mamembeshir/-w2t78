from django.contrib import admin

from .models import Bin, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ("__str__", "warehouse", "code", "is_active")
    list_filter = ("warehouse", "is_active")
    search_fields = ("code", "warehouse__code")
    ordering = ("warehouse", "code")
