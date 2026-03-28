from rest_framework import serializers
from .models import MessageFlag


class SubmitFlagSerializer(serializers.Serializer):
    room_id = serializers.UUIDField()
    message_id = serializers.CharField(max_length=64)
    flagged_session_id = serializers.CharField(max_length=64)
    flagged_username = serializers.CharField(max_length=30)
    reason = serializers.ChoiceField(choices=MessageFlag.REASON_CHOICES)
    detail = serializers.CharField(max_length=300, required=False, allow_blank=True)


class MessageFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageFlag
        fields = [
            "id",
            "room_id",
            "message_id",
            "flagged_username",
            "reporter_username",
            "reason",
            "detail",
            "created_at",
            "is_reviewed",
        ]