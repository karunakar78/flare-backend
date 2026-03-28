import uuid
from django.db import models
from django.utils import timezone


class Room(models.Model):

    TIMER_CHOICES = [
        (30, "30 minutes"),
        (60, "1 hour"),
        (180, "3 hours"),
        (360, "6 hours"),
    ]

    RADIUS_CHOICES = [
        (0.5, "500m"),
        (1.0, "1km"),
        (2.0, "2km"),
        (5.0, "5km"),
    ]

    VISIBILITY_PUBLIC = "public"
    VISIBILITY_INVITE = "invite"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, "Public"),
        (VISIBILITY_INVITE, "Invite Only"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=40)
    topic_tag = models.CharField(max_length=30, blank=True)

    # Creator info — stored directly, not FK, so room outlives session
    creator_id = models.UUIDField(db_index=True)
    creator_username = models.CharField(max_length=30)

    # Location stored as plain lat/lng for now (PostGIS added later)
    latitude = models.FloatField()
    longitude = models.FloatField()

    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PUBLIC,
    )
    invite_code = models.CharField(
        max_length=8, blank=True, null=True, unique=True
    )

    capacity = models.PositiveIntegerField(default=50)
    radius_km = models.FloatField(choices=RADIUS_CHOICES, default=2.0)
    timer_minutes = models.IntegerField(choices=TIMER_CHOICES, default=60)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True, db_index=True)
    last_empty_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "rooms"
        indexes = [
            models.Index(fields=["is_active", "expires_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(
                minutes=self.timer_minutes
            )
        super().save(*args, **kwargs)

    @property
    def current_occupancy(self):
        return self.memberships.filter(is_active=True).count()

    @property
    def is_full(self):
        return self.current_occupancy >= self.capacity

    @property
    def waitlist_count(self):
        return self.waitlist_entries.count()

    def __str__(self):
        return f"{self.name} ({self.id})"


class RoomMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="memberships"
    )
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    username = models.CharField(max_length=30)
    role = models.CharField(max_length=10, default="guest")
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "room_memberships"

    def __str__(self):
        return f"{self.username} in {self.room.name}"


class WaitlistEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="waitlist_entries"
    )
    user_id = models.UUIDField(null=True, blank=True)
    session_id = models.CharField(max_length=64, blank=True)
    username = models.CharField(max_length=30)
    channel_name = models.CharField(max_length=100, blank=True)
    queued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "waitlist_entries"
        ordering = ["queued_at"]

    def __str__(self):
        return f"{self.username} waiting for {self.room.name}"