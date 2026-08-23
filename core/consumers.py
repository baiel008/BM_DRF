import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import Notification


@database_sync_to_async
def user_from_query_string(scope):
    """Достаёт JWT из query-параметра ?token=<access> и возвращает пользователя или None."""
    raw = scope.get("query_string", b"").decode()
    params = dict(p.split("=", 1) for p in raw.split("&") if "=" in p)
    token = params.get("token")
    if not token:
        return None
    try:
        validated = AccessToken(token)
    except TokenError:
        return None
    return get_user_model().objects.filter(pk=validated["user_id"]).first()


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Личный канал пользователя: /ws/notifications/?token=<access>."""

    async def connect(self):
        self.user = await user_from_query_string(self.scope)
        if self.user is None:
            await self.close(code=4001)
            return
        self.group_name = f"user_{self.user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "unread_count":
            count = await database_sync_to_async(
                Notification.objects.filter(user=self.user, is_read=False).count
            )()
            await self.send_json({"type": "unread_count", "data": {"count": count}})
        else:
            await self.send_json({"type": "pong"})

    async def notification(self, event):
        """Хендлер group_send из core.services.notify."""
        await self.send_json({"type": "notification", "data": event["data"]})
