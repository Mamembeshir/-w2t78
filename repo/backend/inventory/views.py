"""
inventory/views.py — Item, ledger, balance, and transaction API views.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, IsInventoryManager
from warehouse.models import Bin, Warehouse

from .costing import InsufficientStockError, post_cycle_count_adjust, post_issue, post_receive, post_transfer
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
from .serializers import (
    CycleCountConfirmSerializer,
    CycleCountSessionSerializer,
    CycleCountStartSerializer,
    CycleCountSubmitSerializer,
    IssueStockSerializer,
    ItemDetailSerializer,
    ItemLotSerializer,
    ItemSerializer,
    ItemSerialSerializer,
    ReceiveStockSerializer,
    StockBalanceSerializer,
    StockLedgerSerializer,
    TransferSerializer,
)

_VARIANCE_THRESHOLD = Decimal("500.00")


# ─────────────────────────────────────────────────────────────────────────────
# Item CRUD
# ─────────────────────────────────────────────────────────────────────────────

class ItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/items/          — list/search items
    POST /api/items/          — create item (Admin/Inventory Manager)
    GET  /api/items/{id}/     — item detail with totals
    PUT/PATCH /api/items/{id}/ — update item
    """

    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ItemDetailSerializer
        return ItemSerializer

    def get_queryset(self):
        qs = Item.objects.filter(deleted_at__isnull=True)
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(sku__icontains=q) | qs.filter(name__icontains=q)
        costing = self.request.query_params.get("costing_method")
        if costing:
            qs = qs.filter(costing_method=costing)
        active = self.request.query_params.get("is_active")
        if active is not None:
            qs = qs.filter(is_active=active.lower() == "true")
        return qs.distinct().order_by("sku")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsInventoryManager()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            return Response(
                {"code": "conflict", "message": "An item with this SKU already exists."},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=True, methods=["get"], url_path="lots")
    def lots(self, request, pk=None):
        item = self.get_object()
        qs = ItemLot.objects.filter(item=item).order_by("received_date")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ItemLotSerializer(page, many=True).data)
        return Response(ItemLotSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="serials")
    def serials(self, request, pk=None):
        item = self.get_object()
        qs = ItemSerial.objects.filter(item=item).order_by("serial_number")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ItemSerialSerializer(page, many=True).data)
        return Response(ItemSerialSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="ledger")
    def ledger(self, request, pk=None):
        item = self.get_object()
        qs = StockLedger.objects.filter(item=item).select_related(
            "warehouse", "bin", "lot", "posted_by"
        ).order_by("-timestamp")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(StockLedgerSerializer(page, many=True).data)
        return Response(StockLedgerSerializer(qs, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# Stock Balance
# ─────────────────────────────────────────────────────────────────────────────

class StockBalanceView(APIView):
    """
    GET /api/inventory/balances/

    Query params:
      warehouse_id  — filter by warehouse
      item_id       — filter by item
      below_safety  — "true" to return only below-safety-stock rows
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = StockBalance.objects.select_related("item", "warehouse", "bin").all()
        warehouse_id = request.query_params.get("warehouse_id")
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        item_id = request.query_params.get("item_id")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if request.query_params.get("below_safety") == "true":
            from django.db.models import F
            qs = qs.filter(quantity_on_hand__lt=F("item__safety_stock_qty"))
        qs = qs.order_by("item__sku", "warehouse__code")

        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(StockBalanceSerializer(page, many=True).data)
        return Response(StockBalanceSerializer(qs, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# Transaction views
# ─────────────────────────────────────────────────────────────────────────────

class ReceiveStockView(APIView):
    """POST /api/inventory/receive/"""

    permission_classes = [IsInventoryManager]

    def post(self, request):
        ser = ReceiveStockSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        item = get_object_or_404(Item, pk=d["item_id"], deleted_at__isnull=True)
        warehouse = get_object_or_404(Warehouse, pk=d["warehouse_id"], deleted_at__isnull=True)
        bin_obj = None
        if d.get("bin_id"):
            bin_obj = get_object_or_404(Bin, pk=d["bin_id"], warehouse=warehouse, deleted_at__isnull=True)
        lot = None
        if d.get("lot_id"):
            lot = get_object_or_404(ItemLot, pk=d["lot_id"], item=item)

        with transaction.atomic():
            ledger = post_receive(
                item=item,
                warehouse=warehouse,
                bin_obj=bin_obj,
                lot=lot,
                quantity=d["quantity"],
                unit_cost=d["unit_cost"],
                reference=d.get("reference", ""),
                posted_by=request.user,
            )
            balance = StockBalance.objects.get(item=item, warehouse=warehouse, bin=bin_obj)

        return Response({
            "ledger_entry": StockLedgerSerializer(ledger).data,
            "balance": StockBalanceSerializer(balance).data,
        }, status=status.HTTP_201_CREATED)


class IssueStockView(APIView):
    """POST /api/inventory/issue/"""

    permission_classes = [IsInventoryManager]

    def post(self, request):
        ser = IssueStockSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        item = get_object_or_404(Item, pk=d["item_id"], deleted_at__isnull=True)
        warehouse = get_object_or_404(Warehouse, pk=d["warehouse_id"], deleted_at__isnull=True)
        bin_obj = None
        if d.get("bin_id"):
            bin_obj = get_object_or_404(Bin, pk=d["bin_id"], warehouse=warehouse, deleted_at__isnull=True)
        lot = None
        if d.get("lot_id"):
            lot = get_object_or_404(ItemLot, pk=d["lot_id"], item=item)

        try:
            with transaction.atomic():
                entries = post_issue(
                    item=item,
                    warehouse=warehouse,
                    bin_obj=bin_obj,
                    lot=lot,
                    quantity=d["quantity"],
                    reference=d.get("reference", ""),
                    posted_by=request.user,
                )
                balance = StockBalance.objects.get(item=item, warehouse=warehouse, bin=bin_obj)
        except InsufficientStockError as exc:
            return Response(
                {"code": "insufficient_stock", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "ledger_entries": StockLedgerSerializer(entries, many=True).data,
            "balance": StockBalanceSerializer(balance).data,
        }, status=status.HTTP_201_CREATED)


class TransferStockView(APIView):
    """POST /api/inventory/transfer/"""

    permission_classes = [IsInventoryManager]

    def post(self, request):
        ser = TransferSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        item = get_object_or_404(Item, pk=d["item_id"], deleted_at__isnull=True)
        from_warehouse = get_object_or_404(Warehouse, pk=d["from_warehouse_id"], deleted_at__isnull=True)
        to_warehouse = get_object_or_404(Warehouse, pk=d["to_warehouse_id"], deleted_at__isnull=True)
        from_bin = None
        if d.get("from_bin_id"):
            from_bin = get_object_or_404(Bin, pk=d["from_bin_id"], warehouse=from_warehouse, deleted_at__isnull=True)
        to_bin = None
        if d.get("to_bin_id"):
            to_bin = get_object_or_404(Bin, pk=d["to_bin_id"], warehouse=to_warehouse, deleted_at__isnull=True)
        lot = None
        if d.get("lot_id"):
            lot = get_object_or_404(ItemLot, pk=d["lot_id"], item=item)

        try:
            with transaction.atomic():
                out_entry, in_entry = post_transfer(
                    item=item,
                    from_warehouse=from_warehouse,
                    from_bin=from_bin,
                    to_warehouse=to_warehouse,
                    to_bin=to_bin,
                    lot=lot,
                    quantity=d["quantity"],
                    reference=d.get("reference", ""),
                    posted_by=request.user,
                )
                from_balance = StockBalance.objects.get(
                    item=item, warehouse=from_warehouse, bin=from_bin
                )
                to_balance = StockBalance.objects.get(
                    item=item, warehouse=to_warehouse, bin=to_bin
                )
        except InsufficientStockError as exc:
            return Response(
                {"code": "insufficient_stock", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "transfer_out": StockLedgerSerializer(out_entry).data,
            "transfer_in": StockLedgerSerializer(in_entry).data,
            "from_balance": StockBalanceSerializer(from_balance).data,
            "to_balance": StockBalanceSerializer(to_balance).data,
        }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# Cycle Count wizard
# ─────────────────────────────────────────────────────────────────────────────

class CycleCountStartView(APIView):
    """POST /api/inventory/cycle-count/start/ — Step 1: open a count session."""

    permission_classes = [IsInventoryManager]

    def post(self, request):
        ser = CycleCountStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        item = get_object_or_404(Item, pk=d["item_id"], deleted_at__isnull=True)
        warehouse = get_object_or_404(Warehouse, pk=d["warehouse_id"], deleted_at__isnull=True)
        bin_obj = None
        if d.get("bin_id"):
            bin_obj = get_object_or_404(Bin, pk=d["bin_id"], warehouse=warehouse, deleted_at__isnull=True)

        balance = StockBalance.objects.filter(
            item=item, warehouse=warehouse, bin=bin_obj
        ).first()
        expected_qty = balance.quantity_on_hand if balance else Decimal("0")

        session = CycleCountSession.objects.create(
            item=item,
            warehouse=warehouse,
            bin=bin_obj,
            expected_qty=expected_qty,
            status=CycleCountStatus.OPEN,
            started_by=request.user,
        )
        return Response(CycleCountSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class CycleCountSubmitView(APIView):
    """POST /api/inventory/cycle-count/{id}/submit/ — Step 2: submit actual count."""

    permission_classes = [IsInventoryManager]

    def post(self, request, pk):
        session = get_object_or_404(CycleCountSession, pk=pk, status=CycleCountStatus.OPEN)
        ser = CycleCountSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        counted_qty = ser.validated_data["counted_qty"]
        variance_qty = counted_qty - session.expected_qty

        balance = StockBalance.objects.filter(
            item=session.item, warehouse=session.warehouse, bin=session.bin
        ).first()
        avg_cost = balance.avg_cost if balance else Decimal("0")
        variance_value = abs(variance_qty) * avg_cost

        session.counted_qty = counted_qty
        session.variance_qty = variance_qty
        session.variance_value = variance_value

        if variance_value > _VARIANCE_THRESHOLD:
            session.status = CycleCountStatus.PENDING_CONFIRM
            session.save()
            return Response({
                "variance_confirmation_required": True,
                "session": CycleCountSessionSerializer(session).data,
            })

        # No confirmation needed — post adjustment immediately
        with transaction.atomic():
            if variance_qty != Decimal("0"):
                ledger = post_cycle_count_adjust(
                    item=session.item,
                    warehouse=session.warehouse,
                    bin_obj=session.bin,
                    variance_qty=variance_qty,
                    unit_cost=avg_cost,
                    reference=f"Cycle count #{session.pk}",
                    posted_by=request.user,
                )
                session.ledger_entry = ledger
            session.status = CycleCountStatus.CONFIRMED
            session.confirmed_by = request.user
            session.save()

        return Response({
            "variance_confirmation_required": False,
            "session": CycleCountSessionSerializer(session).data,
        })


class CycleCountConfirmView(APIView):
    """POST /api/inventory/cycle-count/{id}/confirm/ — Step 3: supervisor confirmation."""

    permission_classes = [IsInventoryManager]

    def post(self, request, pk):
        session = get_object_or_404(CycleCountSession, pk=pk, status=CycleCountStatus.PENDING_CONFIRM)
        ser = CycleCountConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        balance = StockBalance.objects.filter(
            item=session.item, warehouse=session.warehouse, bin=session.bin
        ).first()
        avg_cost = balance.avg_cost if balance else Decimal("0")

        with transaction.atomic():
            if session.variance_qty and session.variance_qty != Decimal("0"):
                ledger = post_cycle_count_adjust(
                    item=session.item,
                    warehouse=session.warehouse,
                    bin_obj=session.bin,
                    variance_qty=session.variance_qty,
                    unit_cost=avg_cost,
                    reference=f"Cycle count #{session.pk} (supervisor confirmed)",
                    posted_by=request.user,
                )
                session.ledger_entry = ledger

            session.reason_code = d["reason_code"]
            session.supervisor_note = d.get("supervisor_note", "")
            session.status = CycleCountStatus.CONFIRMED
            session.confirmed_by = request.user
            session.save()

        return Response(CycleCountSessionSerializer(session).data)
