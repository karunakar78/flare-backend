from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import OTPCode, VerifiedUser


@admin.register(VerifiedUser)
class VerifiedUserAdmin(UserAdmin):
    list_display = ["email", "is_verified", "is_active", "created_at"]
    list_filter = ["is_verified", "is_active"]
    search_fields = ["email"]
    ordering = ["-created_at"]
    fieldsets = (
        (None, {"fields": ("email",)}),
        ("Status", {"fields": ("is_verified", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email",)}),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ["email", "code", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used"]
    search_fields = ["email"]