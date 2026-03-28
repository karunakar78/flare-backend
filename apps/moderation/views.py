from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MessageFlag
from .serializers import SubmitFlagSerializer

AUTO_KICK_THRESHOLD = 3


class SubmitFlagView(APIView):
    """
    POST /api/v1/moderation/flag/
    Anyone (guest or verified) can flag a message.
    Auto-kick fires when a user hits 3 flags in the same room.
    """
    authentication_classes = []

    def post(self, request):
        serializer = SubmitFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payload = request.auth_payload
        reporter_session_id = str(payload.get("user_id", ""))
        reporter_username = payload.get("username", "Anonymous")

        if not reporter_session_id:
            return Response(
                {"detail": "Authentication required to report."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Prevent self-flagging
        if reporter_session_id == data["flagged_session_id"]:
            return Response(
                {"detail": "You cannot report yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create flag — unique constraint prevents duplicate reports
        try:
            MessageFlag.objects.create(
                room_id=data["room_id"],
                message_id=data["message_id"],
                flagged_session_id=data["flagged_session_id"],
                flagged_username=data["flagged_username"],
                reporter_session_id=reporter_session_id,
                reporter_username=reporter_username,
                reason=data["reason"],
                detail=data.get("detail", ""),
            )
        except Exception:
            return Response(
                {"detail": "You have already reported this message."},
                status=status.HTTP_409_CONFLICT,
            )

        # Count total flags for this user in this room
        flag_count = MessageFlag.objects.filter(
            room_id=data["room_id"],
            flagged_session_id=data["flagged_session_id"],
        ).count()

        if flag_count >= AUTO_KICK_THRESHOLD:
            _auto_kick(
                room_id=str(data["room_id"]),
                session_id=data["flagged_session_id"],
                username=data["flagged_username"],
            )
            return Response(
                {"detail": "Report submitted. User has been removed from the room."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"detail": f"Report submitted. ({flag_count}/{AUTO_KICK_THRESHOLD} flags)"},
            status=status.HTTP_201_CREATED,
        )


def _auto_kick(room_id: str, session_id: str, username: str):
    """Deactivates membership when auto-kick threshold is reached."""
    from apps.rooms.models import RoomMembership

    kicked = RoomMembership.objects.filter(
        room_id=room_id,
        session_id=session_id,
        is_active=True,
    ).update(is_active=False)

    if kicked:
        # Check if room is now empty
        from apps.rooms.models import Room
        from django.utils import timezone
        room = Room.objects.filter(id=room_id, is_active=True).first()
        if room and not RoomMembership.objects.filter(room=room, is_active=True).exists():
            room.last_empty_at = timezone.now()
            room.save(update_fields=["last_empty_at"])