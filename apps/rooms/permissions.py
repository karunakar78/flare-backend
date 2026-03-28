from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = "Only verified users can perform this action. Verify your email to unlock room creation."

    def has_permission(self, request, view):
        payload = getattr(request, "auth_payload", {})
        return payload.get("role") == "verified"