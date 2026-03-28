from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


class JWTOrGuestAuthMiddleware(BaseMiddleware):
    """
    Reads JWT from WebSocket query string:
    ws://host/ws/rooms/<id>/?token=<jwt>
    Attaches decoded payload to scope["auth_payload"].
    """
    async def __call__(self, scope, receive, send):
        token = self._extract_token(scope)
        if token:
            payload = await self._decode_token(token)
            scope["auth_payload"] = payload or {}
        else:
            scope["auth_payload"] = {}

        scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)

    @staticmethod
    def _extract_token(scope) -> str | None:
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        tokens = params.get("token", [])
        return tokens[0] if tokens else None

    @database_sync_to_async
    def _decode_token(self, token: str) -> dict | None:
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            decoded = AccessToken(token)
            return {
                "user_id": str(decoded.get("user_id")),
                "username": decoded.get("username", "Anonymous"),
                "role": decoded.get("role", "guest"),
            }
        except Exception:
            return None