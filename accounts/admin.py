"""
accounts/admin.py
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for the User model."""

    list_display = ("username", "email", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Platform Info", {"fields": ("role", "avatar", "bio")}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Platform Info", {"fields": ("role", "email")}),
    )
