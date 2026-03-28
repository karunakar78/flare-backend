from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/rooms/", include("apps.rooms.urls")),
    path("api/v1/moderation/", include("apps.moderation.urls")),
]