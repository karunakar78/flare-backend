import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# This must run before any other Django imports
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.rooms.middleware import JWTOrGuestAuthMiddleware
from apps.rooms.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTOrGuestAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        ),
    }
)