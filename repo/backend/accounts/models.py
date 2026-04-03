"""
accounts/models.py — Custom User model with role-based access control.

Roles:
  ADMIN                — full system access
  INVENTORY_MANAGER    — inventory operations
  PROCUREMENT_ANALYST  — crawling and supplier data
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    INVENTORY_MANAGER = "INVENTORY_MANAGER", "Inventory Manager"
    PROCUREMENT_ANALYST = "PROCUREMENT_ANALYST", "Procurement Analyst"


class User(AbstractUser):
    """
    Custom user model — extends AbstractUser with a role field.

    Argon2 hashing is configured in settings.PASSWORD_HASHERS.
    AbstractUser provides: username, password, first_name, last_name,
    email, is_active, is_staff, last_login, date_joined, etc.
    """

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.INVENTORY_MANAGER,
        db_index=True,
    )

    class Meta:
        db_table = "accounts_user"
        ordering = ["username"]

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def is_inventory_manager(self):
        return self.role == Role.INVENTORY_MANAGER

    @property
    def is_procurement_analyst(self):
        return self.role == Role.PROCUREMENT_ANALYST
