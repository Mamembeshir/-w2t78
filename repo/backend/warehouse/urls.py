"""
warehouse/urls.py — Warehouse and Bin URL patterns.
"""
from django.urls import path

from .views import BinViewSet, WarehouseViewSet

warehouse_list = WarehouseViewSet.as_view({"get": "list", "post": "create"})
warehouse_detail = WarehouseViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"})
bin_list = BinViewSet.as_view({"get": "list", "post": "create"})
bin_detail = BinViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"})

urlpatterns = [
    path("warehouses/", warehouse_list, name="warehouse-list"),
    path("warehouses/<int:pk>/", warehouse_detail, name="warehouse-detail"),
    path("warehouses/<int:warehouse_pk>/bins/", bin_list, name="warehouse-bin-list"),
    path("warehouses/<int:warehouse_pk>/bins/<int:pk>/", bin_detail, name="warehouse-bin-detail"),
]
