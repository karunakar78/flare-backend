import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def close_room_on_expiry(self, room_id: str):
    """Fired at room.expires_at via Celery ETA."""
    try:
        destroy_room.delay(room_id, reason="timer_expired")
    except Exception as exc:
        logger.error(f"[close_room_on_expiry] room={room_id} error={exc}")
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3)
def destroy_room(self, room_id: str, reason: str = "unknown"):
    """
    Central room destruction task.
    1. Marks room inactive
    2. Wipes messages from Redis cache
    3. Clears memberships and waitlist
    """
    from apps.rooms.models import Room, RoomMembership, WaitlistEntry

    try:
        room = Room.objects.get(id=room_id, is_active=True)
    except Room.DoesNotExist:
        logger.info(f"[destroy_room] room={room_id} already inactive, skipping.")
        return

    logger.info(f"[destroy_room] Destroying room={room_id} reason={reason}")

    # 1. Mark room inactive
    room.is_active = False
    room.save(update_fields=["is_active"])

    # 2. Wipe messages from Redis
    from django.core.cache import cache
    cache.delete(f"room:{room_id}:messages")

    # 3. Clear memberships and waitlist
    RoomMembership.objects.filter(room=room, is_active=True).update(is_active=False)
    WaitlistEntry.objects.filter(room=room).delete()

    logger.info(f"[destroy_room] room={room_id} fully destroyed.")


@shared_task
def check_empty_rooms():
    """
    Runs every minute via Celery Beat.
    Destroys rooms that have been empty longer than ROOM_EMPTY_GRACE_MINUTES.
    """
    from apps.rooms.models import Room

    grace_minutes = settings.ROOM_EMPTY_GRACE_MINUTES
    cutoff = timezone.now() - timezone.timedelta(minutes=grace_minutes)

    expired_rooms = Room.objects.filter(
        is_active=True,
        last_empty_at__isnull=False,
        last_empty_at__lte=cutoff,
    )

    for room in expired_rooms:
        logger.info(f"[check_empty_rooms] room={room.id} empty since {room.last_empty_at}, destroying.")
        destroy_room.delay(str(room.id), reason="empty_room")