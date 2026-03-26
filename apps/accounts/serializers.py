from rest_framework import serializers
from .models import VerifiedUser


class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    username = serializers.CharField(max_length=30, min_length=2)


class VerifiedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerifiedUser
        fields = ["id", "email", "is_verified", "created_at"]
        read_only_fields = fields


class GuestSessionSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30, min_length=2)

    def validate_username(self, value):
        value = value.strip()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, hyphens, and underscores."
            )
        return value