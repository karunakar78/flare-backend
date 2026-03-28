import uuid
from django.db import models


class MessageFlag(models.Model):

    REASON_SPAM = "spam"
    REASON_HATE = "hate_speech"
    REASON_HARASSMENT = "harassment"
    REASON_OTHER = "other"

    REASON_CHOICES = [
        (REASON_SPAM, "Spam"),
        (REASON_HATE, "Hate Speech"),
        (REASON_HARASSMENT, "Harassment"),
        (REASON_OTHER, "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Room this flag belongs to
    room_id = models.UUIDField(db_index=True)

    # Message being flagged (timestamp-based ID from Redis, not a DB row)
    message_id = models.CharField(max_length=64, db_index=True)

    # User being flagged
    flagged_session_id = models.CharField(max_length=64, db_index=True)
    flagged_username = models.CharField(max_length=30)

    # Who submitted the flag
    reporter_session_id = models.CharField(max_length=64)
    reporter_username = models.CharField(max_length=30)

    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    detail = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_reviewed = models.BooleanField(default=False)

    class Meta:
        db_table = "message_flags"
        constraints = [
            models.UniqueConstraint(
                fields=["message_id", "reporter_session_id"],
                name="unique_flag_per_reporter_per_message",
            )
        ]
        indexes = [
            models.Index(fields=["room_id", "flagged_session_id"]),
        ]

    def __str__(self):
        return f"Flag on {self.flagged_username} in room {self.room_id} — {self.reason}"