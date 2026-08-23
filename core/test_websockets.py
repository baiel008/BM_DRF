from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from core.services import notify


@database_sync_to_async
def _notify(user, **kwargs):
    return notify(user, **kwargs)


@database_sync_to_async
def _make_notification(user, title):
    from core.models import Notification

    return Notification.objects.create(user=user, title=title)


@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class NotificationWSTestCase(TransactionTestCase):
    def setUp(self):
        from users.models import User

        self.seller = User.objects.create_user(email="ws-seller@test.ru", password="Pass123!", is_seller=True)
        self.other = User.objects.create_user(email="ws-other@test.ru", password="Pass123!")

    def _comm(self, user=None, token=None):
        if token is None and user is not None:
            token = str(AccessToken.for_user(user))
        query = f"?token={token}" if token else ""
        return WebsocketCommunicator(application, f"/ws/notifications/{query}")

    async def test_connect_and_receive_notification(self):
        comm = self._comm(self.seller)
        connected, _ = await comm.connect()
        self.assertTrue(connected)

        notification = await _notify(
            self.seller,
            type="order.paid",
            title="Заказ оплачен",
            text="Тест",
            link="/api/orders/1/",
        )
        message = await comm.receive_json_from(timeout=5)
        self.assertEqual(message["type"], "notification")
        self.assertEqual(message["data"]["id"], notification.pk)
        self.assertEqual(message["data"]["title"], "Заказ оплачен")

        await comm.disconnect()

    async def test_other_users_notifications_not_delivered(self):
        comm = self._comm(self.seller)
        await comm.connect()
        await _notify(self.other, type="order.paid", title="Чужое")
        # своё событие не пришло; проверяем живость канала понгом
        await comm.send_to(text_data='{"action": "ping"}')
        message = await comm.receive_json_from(timeout=5)
        self.assertEqual(message["type"], "pong")
        await comm.disconnect()

    async def test_invalid_token_rejected(self):
        comm = self._comm(token="garbage-token")
        connected, code = await comm.connect()
        self.assertFalse(connected)

    async def test_missing_token_rejected(self):
        comm = self._comm(token="")
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_unread_count_action(self):
        await _make_notification(self.seller, "Раз")
        await _make_notification(self.seller, "Два")
        comm = self._comm(self.seller)
        await comm.connect()
        await comm.send_to(text_data='{"action": "unread_count"}')
        message = await comm.receive_json_from(timeout=5)
        self.assertEqual(message["type"], "unread_count")
        self.assertEqual(message["data"]["count"], 2)
        await comm.disconnect()
