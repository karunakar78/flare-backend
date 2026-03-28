from django.contrib import admin
from .models import MessageFlag


@admin.register(MessageFlag)
class MessageFlagAdmin(admin.ModelAdmin):
    list_display = [
        "flagged_username", "reason", "room_id",
        "reporter_username", "is_reviewed", "created_at",
    ]
    list_filter = ["reason", "is_reviewed"]
    search_fields = ["flagged_username", "reporter_username"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-created_at"]

    actions = ["mark_reviewed"]

    @admin.action(description="Mark selected flags as reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(is_reviewed=True)