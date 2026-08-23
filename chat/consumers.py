from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from core.consumers import user_from_query_string
from .models import Message, Thread


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Чат по заказу: /ws/chat/<thread_id>/?token=<access>."""

    async def connect(self):
        self.user = await user_from_query_string(self.scope)
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        has_access = False
        if self.user is not None:
            has_access = await database_sync_to_async(self._check_access)()
        if not has_access:
            await self.close(code=4003)
            return
        self.group_name = f"chat_{self.thread_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    def _check_access(self):
        thread = Thread.objects.filter(pk=self.thread_id).first()
        return bool(thread and thread.has_access(self.user))

    @database_sync_to_async
    def _save_and_notify(self, text):
        from core.services import notify

        thread = Thread.objects.get(pk=self.thread_id)
        message = Message.objects.create(thread=thread, sender=self.user, text=text)
        payload = {
            "id": message.pk,
            "thread": message.thread_id,
            "sender_id": message.sender_id,
            "sender_name": message.sender.get_full_name() or message.sender.email,
            "text": message.text,
            "created_at": message.created_at.isoformat(),
        }
        sender_name = payload["sender_name"]
        for user in thread.others(self.user):
            notify(
                user,
                type="chat.message",
                title="Новое сообщение",
                text=f"{sender_name}: {message.text[:80]}",
                link=f"/api/chat/threads/{message.thread_id}/messages/",
            )
        return payload

    async def receive_json(self, content, **kwargs):
        text = (content.get("text") or "").strip()
        if not text:
            await self.send_json({"type": "error", "data": {"error": "Пустое сообщение"}})
            return
        data = await self._save_and_notify(text[:2000])
        await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "data": data})

    async def chat_message(self, event):
        """Хендлер broadcast в группу диалога."""
        await self.send_json(event)
