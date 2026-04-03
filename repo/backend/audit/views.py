"""
audit/views.py — Read-only audit log API (Admin only).

GET /api/audit/  — paginated list, filterable by user/model/action/date range.
"""
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsAdmin
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "user", "action", "model_name", "object_id", "changes", "ip_address", "timestamp")

    def get_user(self, obj):
        return obj.user.username if obj.user else "system"


class AuditLogView(APIView):
    """
    GET /api/audit/

    Query params:
      user_id    — filter by user FK
      model      — filter by model_name (case-insensitive contains)
      action     — CREATE | UPDATE | DELETE
      from_date  — ISO date, inclusive
      to_date    — ISO date, inclusive
    """

    permission_classes = [IsAdmin]

    def get(self, request):
        qs = AuditLog._default_manager.select_related("user").order_by("-timestamp")

        user_id = request.query_params.get("user_id")
        if user_id:
            qs = qs.filter(user_id=user_id)

        model = request.query_params.get("model")
        if model:
            qs = qs.filter(model_name__icontains=model)

        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action.upper())

        from_date = request.query_params.get("from_date")
        if from_date:
            qs = qs.filter(timestamp__date__gte=from_date)

        to_date = request.query_params.get("to_date")
        if to_date:
            qs = qs.filter(timestamp__date__lte=to_date)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
        return Response(AuditLogSerializer(qs, many=True).data)
