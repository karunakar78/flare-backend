import math
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Room, RoomMembership, WaitlistEntry
from .serializers import RoomCreateSerializer, RoomDetailSerializer, RoomListSerializer
from .permissions import IsVerifiedUser


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class RoomDiscoveryView(APIView):
    """
    GET /api/v1/rooms/?lat=12.97&lng=77.59&radius_km=2
    """

    authentication_classes = []

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "lat and lng query params are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        radius_km = float(request.query_params.get("radius_km", 2.0))

        # Fetch all active public rooms and filter by radius in Python
        # (PostGIS will replace this in a later step)
        rooms = Room.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now(),
            visibility=Room.VISIBILITY_PUBLIC,
        )

        nearby = []
        for room in rooms:
            dist = haversine_km(lat, lng, room.latitude, room.longitude)
            if dist <= radius_km and dist <= room.radius_km and not room.is_full:
                nearby.append(room)

        nearby.sort(key=lambda r: haversine_km(lat, lng, r.latitude, r.longitude))

        serializer = RoomListSerializer(nearby, many=True, context={"request": request})
        return Response(serializer.data)


class RoomCreateView(APIView):
    authentication_classes = []
    permission_classes = [IsVerifiedUser]

    def post(self, request):
        serializer = RoomCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        room = serializer.save()

        from apps.rooms.tasks import close_room_on_expiry
        close_room_on_expiry.apply_async(
            args=[str(room.id)],
            eta=room.expires_at,
        )

        return Response(
            RoomDetailSerializer(room, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RoomDetailView(APIView):
    """
    GET    /api/v1/rooms/<id>/
    DELETE /api/v1/rooms/<id>/  — creator only
    """

    authentication_classes = []

    def _get_room(self, room_id):
        try:
            return Room.objects.get(id=room_id, is_active=True)
        except Room.DoesNotExist:
            return None

    def get(self, request, room_id):
        room = self._get_room(room_id)
        if not room:
            return Response(
                {"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if room.visibility == Room.VISIBILITY_INVITE:
            code = request.query_params.get("invite_code")
            is_creator = str(request.auth_payload.get("user_id")) == str(
                room.creator_id
            )
            if not is_creator and code != room.invite_code:
                return Response(
                    {"detail": "Invalid invite code."}, status=status.HTTP_403_FORBIDDEN
                )

        return Response(RoomDetailSerializer(room, context={"request": request}).data)

    def delete(self, request, room_id):
        room = self._get_room(room_id)
        if not room:
            return Response(
                {"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if str(request.auth_payload.get("user_id")) != str(room.creator_id):
            return Response(
                {"detail": "Only the room creator can close this room."},
                status=status.HTTP_403_FORBIDDEN,
            )

        room.is_active = False
        room.save(update_fields=["is_active"])
        return Response({"detail": "Room closed."}, status=status.HTTP_200_OK)


class JoinRoomView(APIView):
    """
    POST /api/v1/rooms/<id>/join/
    """

    authentication_classes = []

    def post(self, request, room_id):
        room = Room.objects.filter(id=room_id, is_active=True).first()
        if not room:
            return Response(
                {"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND
            )

        payload = request.auth_payload
        if not payload:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        session_id = payload.get("user_id")
        username = payload.get("username", "Anonymous")
        role = payload.get("role", "guest")
        user_id = session_id if role == "verified" else None

        # Already a member?
        if RoomMembership.objects.filter(
            room=room, session_id=str(session_id), is_active=True
        ).exists():
            return Response({"detail": "Already in this room.", "status": "joined"})

        if room.is_full:
            WaitlistEntry.objects.get_or_create(
                room=room,
                session_id=str(session_id),
                defaults={"username": username, "user_id": user_id},
            )
            return Response(
                {"detail": "Room is full. Added to waitlist.", "status": "waitlisted"},
                status=status.HTTP_202_ACCEPTED,
            )

        RoomMembership.objects.create(
            room=room,
            session_id=str(session_id),
            user_id=user_id,
            username=username,
            role=role,
        )
        return Response(
            {"detail": "Joined room.", "status": "joined"}, status=status.HTTP_200_OK
        )


class LeaveRoomView(APIView):
    authentication_classes = []

    def post(self, request, room_id):
        room = Room.objects.filter(id=room_id, is_active=True).first()
        if not room:
            return Response(
                {"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND
            )

        payload = request.auth_payload
        session_id = payload.get("user_id")

        RoomMembership.objects.filter(
            room=room,
            session_id=str(session_id),
            is_active=True,
        ).update(is_active=False)

        # If room is now empty, record the time for grace period check
        if not RoomMembership.objects.filter(room=room, is_active=True).exists():
            room.last_empty_at = timezone.now()
            room.save(update_fields=["last_empty_at"])

        return Response({"detail": "Left room."}, status=status.HTTP_200_OK)
