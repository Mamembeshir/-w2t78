"""
accounts/permissions.py — DRF permission classes for role-based access control.

Usage:
  from accounts.permissions import IsAdmin, IsInventoryManager, IsProcurementAnalyst

Rules:
  IsAdmin               — ADMIN role only
  IsInventoryManager    — ADMIN or INVENTORY_MANAGER
  IsProcurementAnalyst  — ADMIN or PROCUREMENT_ANALYST
  IsAdminOrReadOnly     — ADMIN for writes; any authenticated user for safe methods
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


class IsAdmin(BasePermission):
    """Only users with ADMIN role may access."""

    message = "You must have Admin role to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ADMIN
        )


class IsInventoryManager(BasePermission):
    """ADMIN and INVENTORY_MANAGER may access."""

    message = "You must have Inventory Manager (or Admin) role to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.ADMIN, Role.INVENTORY_MANAGER)
        )


class IsProcurementAnalyst(BasePermission):
    """ADMIN and PROCUREMENT_ANALYST may access."""

    message = "You must have Procurement Analyst (or Admin) role to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.ADMIN, Role.PROCUREMENT_ANALYST)
        )


class IsAdminOrReadOnly(BasePermission):
    """
    ADMIN may write (POST/PUT/PATCH/DELETE).
    Any authenticated user may read (GET/HEAD/OPTIONS).
    Used for reference-data endpoints (warehouses, items, etc.).
    """

    message = "You must have Admin role to modify this resource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == Role.ADMIN
