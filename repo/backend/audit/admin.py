from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_id", "ip_address")
    list_filter = ("action", "model_name")
    search_fields = ("user__username", "model_name", "object_id", "ip_address")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"
    readonly_fields = (
        "user", "action", "model_name", "object_id", "changes", "ip_address", "timestamp",
        "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
