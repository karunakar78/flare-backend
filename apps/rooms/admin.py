from django.contrib import admin
from .models import Room, RoomMembership, WaitlistEntry


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["name", "topic_tag", "creator_username", "is_active", "capacity", "expires_at"]
    list_filter = ["is_active", "visibility"]
    search_fields = ["name", "creator_username"]
    readonly_fields = ["id", "created_at", "expires_at"]


@admin.register(RoomMembership)
class RoomMembershipAdmin(admin.ModelAdmin):
    list_display = ["username", "role", "room", "is_active", "joined_at"]


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ["username", "room", "queued_at"]