import json
import logging
from django.core.cache import cache
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

MAX_MESSAGES_CACHED = 100


class RoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a chat room.

    Connect:  ws://host/ws/rooms/<room_id>/?token=<jwt>

    Client → Server:
        { "type": "message", "text": "hello" }
        { "type": "kick", "session_id": "<id>" }   # creator only

    Server → Client:
        { "type": "message", ... }
        { "type": "user_joined", ... }
        { "type": "user_left", ... }
        { "type": "user_kicked", ... }
        { "type": "room_closed", "reason": "..." }
        { "type": "error", "detail": "..." }
    """

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"room_{self.room_id}"
        self.user_payload = self.scope.get("auth_payload", {})
        self.session_id = str(self.user_payload.get("user_id", ""))
        self.username = self.user_payload.get("username", "Anonymous")
        self.role = self.user_payload.get("role", "guest")

        # Validate room exists and is active
        room = await self._get_room()
        if not room:
            await self.close(code=4004)
            return

        # Must have joined via REST first
        is_member = await self._is_member()
        if not is_member:
            await self.close(code=4003)
            return

        # Join the channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Broadcast user_joined to room
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user.joined",
                "session_id": self.session_id,
                "username": self.username,
                "role": self.role,
            },
        )

        # Send message history to new joiner
        history = cache.get(f"room:{self.room_id}:messages", [])
        for msg in history:
            await self.send(text_data=json.dumps(msg))

        logger.info(f"[RoomConsumer] {self.username} connected to room {self.room_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        await self._deactivate_membership()

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user.left",
                "session_id": self.session_id,
                "username": self.username,
            },
        )

        await self._maybe_mark_empty()

        logger.info(f"[RoomConsumer] {self.username} disconnected from room {self.room_id}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON.")
            return

        msg_type = data.get("type")

        if msg_type == "message":
            await self._handle_message(data)
        elif msg_type == "kick":
            await self._handle_kick(data)
        else:
            await self._send_error(f"Unknown type: {msg_type}")

    # --- Inbound handlers ---

    async def _handle_message(self, data):
        text = (data.get("text") or "").strip()
        if not text:
            return
        if len(text) > 500:
            await self._send_error("Message too long (max 500 chars).")
            return

        message = {
            "type": "chat.message",      # routes to chat_message handler
            "session_id": self.session_id,
            "username": self.username,
            "role": self.role,
            "text": text,
            "timestamp": timezone.now().isoformat(),
        }

        self._append_to_cache(self.room_id, {**message, "type": "message"})

        await self.channel_layer.group_send(self.group_name, message)

    async def _handle_kick(self, data):
        is_creator = await self._is_creator()
        if not is_creator:
            await self._send_error("Only the room creator can kick users.")
            return

        target = data.get("session_id")
        if not target:
            await self._send_error("session_id is required.")
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user.kicked",
                "session_id": target,
                "kicked_by": self.username,
            },
        )

    # --- Outbound handlers ---

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "session_id": event["session_id"],
            "username": event["username"],
            "role": event["role"],
            "text": event["text"],
            "timestamp": event["timestamp"],
        }))

    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_joined",
            "username": event["username"],
            "role": event["role"],
        }))

    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_left",
            "username": event["username"],
        }))

    async def user_kicked(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_kicked",
            "session_id": event["session_id"],
            "kicked_by": event["kicked_by"],
        }))
        # Close connection if this client was kicked
        if event["session_id"] == self.session_id:
            await self.close(code=4005)

    async def room_closed(self, event):
        await self.send(text_data=json.dumps({
            "type": "room_closed",
            "reason": event.get("reason", "unknown"),
        }))
        await self.close(code=4000)

    # --- DB helpers ---

    @database_sync_to_async
    def _get_room(self):
        from apps.rooms.models import Room
        return Room.objects.filter(id=self.room_id, is_active=True).first()

    @database_sync_to_async
    def _is_member(self):
        from apps.rooms.models import RoomMembership
        return RoomMembership.objects.filter(
            room_id=self.room_id,
            session_id=self.session_id,
            is_active=True,
        ).exists()

    @database_sync_to_async
    def _is_creator(self):
        from apps.rooms.models import Room
        return Room.objects.filter(
            id=self.room_id,
            creator_id=self.session_id,
        ).exists()

    @database_sync_to_async
    def _deactivate_membership(self):
        from apps.rooms.models import RoomMembership
        RoomMembership.objects.filter(
            room_id=self.room_id,
            session_id=self.session_id,
            is_active=True,
        ).update(is_active=False)

    @database_sync_to_async
    def _maybe_mark_empty(self):
        from apps.rooms.models import Room, RoomMembership
        from django.utils import timezone
        active_count = RoomMembership.objects.filter(
            room_id=self.room_id, is_active=True
        ).count()
        if active_count == 0:
            Room.objects.filter(id=self.room_id).update(
                last_empty_at=timezone.now()
            )

    # --- Cache helper ---

    @staticmethod
    def _append_to_cache(room_id: str, message: dict):
        key = f"room:{room_id}:messages"
        messages = cache.get(key, [])
        messages.append(message)
        if len(messages) > MAX_MESSAGES_CACHED:
            messages = messages[-MAX_MESSAGES_CACHED:]
        cache.set(key, messages, timeout=None)

    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))