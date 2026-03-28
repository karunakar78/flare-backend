import math
from rest_framework import serializers
from .models import Room


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Straight-line distance between two GPS points in km."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class RoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = [
            "name",
            "topic_tag",
            "radius_km",
            "timer_minutes",
            "capacity",
            "visibility",
            "latitude",
            "longitude",
        ]

    def validate_topic_tag(self, value):
        if value and not value.startswith("#"):
            value = f"#{value}"
        return value.lower()

    def create(self, validated_data):
        request = self.context["request"]
        payload = request.auth_payload

        validated_data["creator_id"] = payload["user_id"]
        validated_data["creator_username"] = payload["username"]

        if validated_data.get("visibility") == Room.VISIBILITY_INVITE:
            import secrets
            validated_data["invite_code"] = secrets.token_urlsafe(6)[:8]

        return super().create(validated_data)


class RoomListSerializer(serializers.ModelSerializer):
    current_occupancy = serializers.IntegerField(read_only=True)
    waitlist_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    seconds_remaining = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            "id",
            "name",
            "topic_tag",
            "creator_username",
            "radius_km",
            "capacity",
            "current_occupancy",
            "waitlist_count",
            "is_full",
            "visibility",
            "latitude",
            "longitude",
            "distance_km",
            "expires_at",
            "seconds_remaining",
            "created_at",
        ]

    def get_seconds_remaining(self, obj):
        from django.utils import timezone
        delta = obj.expires_at - timezone.now()
        return max(int(delta.total_seconds()), 0)

    def get_distance_km(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
            return round(haversine_km(lat, lng, obj.latitude, obj.longitude), 2)
        except (TypeError, ValueError):
            return None


class RoomDetailSerializer(RoomListSerializer):
    invite_code = serializers.CharField(read_only=True)

    class Meta(RoomListSerializer.Meta):
        fields = RoomListSerializer.Meta.fields + ["invite_code"]