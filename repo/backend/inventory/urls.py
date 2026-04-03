"""
inventory/urls.py
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CycleCountConfirmView,
    CycleCountStartView,
    CycleCountSubmitView,
    IssueStockView,
    ItemViewSet,
    ReceiveStockView,
    StockBalanceView,
    TransferStockView,
)

router = DefaultRouter()
router.register(r"items", ItemViewSet, basename="item")

urlpatterns = router.urls + [
    path("inventory/balances/", StockBalanceView.as_view(), name="inventory-balances"),
    path("inventory/receive/", ReceiveStockView.as_view(), name="inventory-receive"),
    path("inventory/issue/", IssueStockView.as_view(), name="inventory-issue"),
    path("inventory/transfer/", TransferStockView.as_view(), name="inventory-transfer"),
    path("inventory/cycle-count/start/", CycleCountStartView.as_view(), name="cycle-count-start"),
    path("inventory/cycle-count/<int:pk>/submit/", CycleCountSubmitView.as_view(), name="cycle-count-submit"),
    path("inventory/cycle-count/<int:pk>/confirm/", CycleCountConfirmView.as_view(), name="cycle-count-confirm"),
]
