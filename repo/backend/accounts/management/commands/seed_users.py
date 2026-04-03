"""
accounts/management/commands/seed_users.py

Creates one default account per role so the platform is usable immediately
after `docker compose up` without any manual setup.

Idempotent — skips any username that already exists.

Usage:
    python manage.py seed_users
"""
from django.core.management.base import BaseCommand

from accounts.models import Role, User

SEED_ACCOUNTS = [
    {
        "username": "admin",
        "password": "Wh@reH0use!",
        "role": Role.ADMIN,
        "first_name": "System",
        "last_name": "Admin",
        "email": "admin@warehouse.local",
    },
    {
        "username": "inv_manager",
        "password": "St0ck!Ctrl99",
        "role": Role.INVENTORY_MANAGER,
        "first_name": "Inventory",
        "last_name": "Manager",
        "email": "inv.manager@warehouse.local",
    },
    {
        "username": "analyst",
        "password": "Pr0cur3!Analy",
        "role": Role.PROCUREMENT_ANALYST,
        "first_name": "Procurement",
        "last_name": "Analyst",
        "email": "analyst@warehouse.local",
    },
]


class Command(BaseCommand):
    help = "Seed one default user account per role (idempotent)."

    def handle(self, *args, **options):
        created_count = 0
        for account in SEED_ACCOUNTS:
            username = account["username"]
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  skip  {username} (already exists)")
                continue

            user = User(
                username=username,
                role=account["role"],
                first_name=account["first_name"],
                last_name=account["last_name"],
                email=account["email"],
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )
            user.set_password(account["password"])
            user.save()
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f"  created {username} [{account['role']}]")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed complete. {created_count} account(s) created."
            )
        )
