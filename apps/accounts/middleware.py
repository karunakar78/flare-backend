from rest_framework_simplejwt.tokens import AccessToken


class JWTAuthMiddleware:
    """
    Decodes the JWT from the Authorization header and attaches
    the payload to request.auth_payload for use in views.
    Works for both guest and verified tokens.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.auth_payload = {}
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                decoded = AccessToken(token)
                request.auth_payload = {
                    "user_id": str(decoded.get("user_id")),
                    "username": decoded.get("username", "Anonymous"),
                    "role": decoded.get("role", "guest"),
                }
            except Exception:
                pass
        return self.get_response(request)