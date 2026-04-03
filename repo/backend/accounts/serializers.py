"""
accounts/serializers.py — Serializers for User model and auth endpoints.
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Full user representation.

    password — write-only; required on create, omitted on update.
               Validated against settings.AUTH_PASSWORD_VALIDATORS (min 10 chars, etc).
               Always stored as Argon2 hash via User.set_password().
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "last_login",
            "date_joined",
        )
        read_only_fields = ("id", "last_login", "date_joined")

    def validate(self, attrs):
        # Password is required when creating a new user
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required when creating a user."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Enforce safe defaults — API users can never become superusers or staff
        validated_data.setdefault("is_staff", False)
        validated_data["is_superuser"] = False
        user = User(**validated_data)
        user.set_password(password)  # hashes with Argon2
        user.save()
        return user

    def update(self, instance, validated_data):
        # Password changes go through the reset-password endpoint — never via PUT/PATCH
        validated_data.pop("password", None)
        # Never allow elevation to superuser/staff via this endpoint
        validated_data.pop("is_superuser", None)
        validated_data.pop("is_staff", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class PasswordResetSerializer(serializers.Serializer):
    """Used by the reset-password admin action."""

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )


class RegisterSerializer(serializers.ModelSerializer):
    """
    Public self-registration.  Always creates a PROCUREMENT_ANALYST account.
    Role is fixed server-side and cannot be supplied by the client.
    """

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = ("username", "password", "email", "first_name", "last_name")

    def create(self, validated_data):
        from .models import Role
        password = validated_data.pop("password")
        user = User(
            **validated_data,
            role=Role.PROCUREMENT_ANALYST,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        user.set_password(password)
        user.save()
        return user
