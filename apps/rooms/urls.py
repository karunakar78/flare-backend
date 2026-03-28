from django.urls import path
from .views import JoinRoomView, LeaveRoomView, RoomCreateView, RoomDetailView, RoomDiscoveryView

urlpatterns = [
    path("", RoomDiscoveryView.as_view(), name="room-discovery"),
    path("create/", RoomCreateView.as_view(), name="room-create"),
    path("<uuid:room_id>/", RoomDetailView.as_view(), name="room-detail"),
    path("<uuid:room_id>/join/", JoinRoomView.as_view(), name="room-join"),
    path("<uuid:room_id>/leave/", LeaveRoomView.as_view(), name="room-leave"),
]