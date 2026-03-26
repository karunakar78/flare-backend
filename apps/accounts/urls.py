from django.urls import path
from .views import GuestEntryView, MeView, RequestOTPView, VerifyOTPView

urlpatterns = [
    path("guest/", GuestEntryView.as_view(), name="guest-entry"),
    path("otp/request/", RequestOTPView.as_view(), name="otp-request"),
    path("otp/verify/", VerifyOTPView.as_view(), name="otp-verify"),
    path("me/", MeView.as_view(), name="me"),
]