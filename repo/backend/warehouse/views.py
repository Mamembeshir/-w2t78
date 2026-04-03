"""
warehouse/views.py — Warehouse and Bin API views.

Permissions:
  - Warehouse list/detail: any authenticated user
  - Warehouse create/update: Admin only
  - Bin list: any authenticated user (scoped to warehouse)
  - Bin create/update: Admin only
"""
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdmin
from .models import Bin, Warehouse
from .serializers import BinSerializer, WarehouseSerializer


class WarehouseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/warehouses/        — list (any authenticated)
    POST /api/warehouses/        — create (Admin)
    GET  /api/warehouses/{id}/   — detail (any authenticated)
    PUT/PATCH /api/warehouses/{id}/ — update (Admin)
    """

    serializer_class = WarehouseSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return Warehouse.objects.filter(deleted_at__isnull=True).order_by("code")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsAdmin()]
        return [IsAuthenticated()]


class BinViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/warehouses/{warehouse_pk}/bins/        — list bins
    POST /api/warehouses/{warehouse_pk}/bins/        — create bin (Admin)
    GET  /api/warehouses/{warehouse_pk}/bins/{id}/   — detail
    PUT/PATCH /api/warehouses/{warehouse_pk}/bins/{id}/ — update (Admin)
    """

    serializer_class = BinSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return Bin.objects.filter(
            warehouse_id=self.kwargs["warehouse_pk"],
            deleted_at__isnull=True,
        ).order_by("code")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(warehouse_id=self.kwargs["warehouse_pk"])
