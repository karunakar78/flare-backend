import random
import string
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode, VerifiedUser
from .serializers import (
    GuestSessionSerializer,
    RequestOTPSerializer,
    VerifiedUserSerializer,
    VerifyOTPSerializer,
)


def _make_guest_token(username: str) -> dict:
    token = RefreshToken()
    token["user_id"] = str(uuid.uuid4())
    token["role"] = "guest"
    token["username"] = username
    return {
        "access": str(token.access_token),
        "refresh": str(token),
        "role": "guest",
        "username": username,
    }


def _make_verified_token(user: VerifiedUser, username: str) -> dict:
    token = RefreshToken.for_user(user)
    token["role"] = "verified"
    token["username"] = username
    return {
        "access": str(token.access_token),
        "refresh": str(token),
        "role": "verified",
        "username": username,
        "user": VerifiedUserSerializer(user).data,
    }


class GuestEntryView(APIView):
    """
    POST /api/v1/auth/guest/
    No signup required. Returns a JWT with role=guest.
    """
    def post(self, request):
        serializer = GuestSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        return Response(_make_guest_token(username), status=status.HTTP_200_OK)


class RequestOTPView(APIView):
    """
    POST /api/v1/auth/otp/request/
    Sends a 6-digit OTP to the provided email.
    """
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Get or create unverified user
        VerifiedUser.objects.get_or_create(email=email)

        # Invalidate any existing OTPs
        OTPCode.objects.filter(email=email, is_used=False).update(is_used=True)

        # Generate OTP
        code = "".join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        OTPCode.objects.create(email=email, code=code, expires_at=expires_at)

        # Send email
        send_mail(
            subject="Your Flare verification code",
            message=f"Your OTP is: {code}\n\nExpires in {settings.OTP_EXPIRY_MINUTES} minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({"detail": "OTP sent to your email."}, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """
    POST /api/v1/auth/otp/verify/
    Validates OTP, marks user verified, returns a JWT.
    """
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        username = serializer.validated_data["username"]

        try:
            otp = OTPCode.objects.get(email=email, code=code, is_used=False)
        except OTPCode.DoesNotExist:
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp.is_valid():
            return Response(
                {"detail": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        user = VerifiedUser.objects.get(email=email)
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        return Response(_make_verified_token(user, username), status=status.HTTP_200_OK)


class MeView(APIView):
    """
    GET /api/v1/auth/me/
    Returns current verified user details.
    """
    authentication_classes = []
    
    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Not authenticated."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(VerifiedUserSerializer(request.user).data)