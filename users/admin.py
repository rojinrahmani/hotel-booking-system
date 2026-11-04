from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Built-in user admin plus the hotel-specific fields.

    There is no user API (out of scope), so the admin is the way to create guests.
    """

    fieldsets = (
        *BaseUserAdmin.fieldsets,
        ("Guest details", {"fields": ("id_card", "phone", "gender")}),
    )
    add_fieldsets = (
        *BaseUserAdmin.add_fieldsets,
        ("Guest details", {"fields": ("email", "id_card", "phone", "gender")}),
    )
    list_display = ("id", "username", "email", "id_card", "phone", "gender", "is_staff")
    list_filter = (*BaseUserAdmin.list_filter, "gender")
    search_fields = ("username", "email", "id_card", "phone")
