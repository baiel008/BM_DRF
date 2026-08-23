from decimal import Decimal
from io import BytesIO

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APITestCase

from catalog.models import Category, Product
from config.asgi import application
from core.models import Notification
from orders.models import Order, OrderItem, PaymentMethod
from shops.models import Shop
from users.models import User

from .models import Message, Thread


def _make_order(buyer, shop, category):
    product = Product.objects.create(shop=shop, category=category, name="Крем", price=Decimal("1000"), stock=10)
    order = Order.objects.create(
        user=buyer,
        payment_method=PaymentMethod.CASH,
        recipient_name="Иван",
        phone="+996 700 000 000",
        address="Бишкек, пр. Чуй 1",
        total=Decimal("1000"),
    )
    OrderItem.objects.create(
        order=order, product=product, shop=shop,
        product_name=product.name, price=Decimal("1000"), quantity=1, subtotal=Decimal("1000"),
    )
    return order


class ChatRESTTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="chat-seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="chat-buyer@test.ru", password="Pass123!")
        self.stranger = User.objects.create_user(email="chat-stranger@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин", city="Бишкек")
        self.category = Category.objects.create(name="Категория")
        self.order = _make_order(self.buyer, self.shop, self.category)

    def login(self, user):
        token = self.client.post("/api/auth/login/", {"email": user.email, "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_thread_create_for_order(self):
        self.login(self.buyer)
        resp = self.client.post(f"/api/chat/orders/{self.order.pk}/thread/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        thread_id = resp.data["id"]
        resp = self.client.post(f"/api/chat/orders/{self.order.pk}/thread/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], thread_id)
        self.assertFalse(resp.data["created"])

    def test_threads_visible_to_buyer_and_seller(self):
        Thread.objects.create(order=self.order)
        self.login(self.buyer)
        resp = self.client.get("/api/chat/threads/")
        self.assertEqual(resp.data["count"], 1)
        self.login(self.seller)
        resp = self.client.get("/api/chat/threads/")
        self.assertEqual(resp.data["count"], 1)

    def test_stranger_has_no_access(self):
        thread = Thread.objects.create(order=self.order)
        self.login(self.stranger)
        resp = self.client.post(f"/api/chat/orders/{self.order.pk}/thread/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        resp = self.client.get(f"/api/chat/threads/{thread.pk}/messages/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_reading_messages_marks_them_read(self):
        thread = Thread.objects.create(order=self.order)
        Message.objects.create(thread=thread, sender=self.seller, text="Здравствуйте!")
        self.login(self.buyer)
        resp = self.client.get(f"/api/chat/threads/{thread.pk}/messages/")
        self.assertEqual(resp.data["count"], 1)
        message = Message.objects.get(thread=thread)
        self.assertTrue(message.is_read)

    # ─── Диалоги по товару / магазину ──────────────────────────────────────────

    def _png(self):
        buf = BytesIO()
        Image.new("RGB", (10, 10), "red").save(buf, format="PNG")
        return SimpleUploadedFile("photo.png", buf.getvalue(), content_type="image/png")

    def test_thread_create_for_product(self):
        product = Product.objects.create(
            shop=self.shop, category=self.category, name="Сыворотка", price=Decimal("500"), stock=5
        )
        self.login(self.buyer)
        resp = self.client.post("/api/chat/threads/create/", {"product_id": product.pk}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        thread_id = resp.data["id"]
        self.assertEqual(resp.data["product_name"], "Сыворотка")
        # Повторно — тот же диалог
        resp = self.client.post("/api/chat/threads/create/", {"product_id": product.pk}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["created"])
        # Продавец видит диалог в списке и имеет доступ
        self.login(self.seller)
        resp = self.client.get("/api/chat/threads/")
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["id"], thread_id)

    def test_thread_create_for_shop(self):
        self.login(self.buyer)
        resp = self.client.post("/api/chat/threads/create/", {"shop_id": self.shop.pk}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("Магазин", resp.data["title"])

    def test_thread_create_validation_errors(self):
        self.login(self.buyer)
        # Ни одного контекста
        resp = self.client.post("/api/chat/threads/create/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Оба сразу
        resp = self.client.post(
            "/api/chat/threads/create/",
            {"shop_id": self.shop.pk, "product_id": 999},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Свой магазин
        self.login(self.seller)
        resp = self.client.post("/api/chat/threads/create/", {"shop_id": self.shop.pk}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rest_message_with_attachment(self):
        thread = Thread.objects.create(order=self.order, initiator=self.buyer)
        self.login(self.buyer)
        before = Notification.objects.count()
        resp = self.client.post(
            f"/api/chat/threads/{thread.pk}/messages/send/",
            {"text": "Вот фото", "attachment": self._png()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["attachment"])
        self.assertEqual(Notification.objects.count(), before + 1)
        # Чужой не может писать в чужой диалог
        self.login(self.stranger)
        resp = self.client.post(
            f"/api/chat/threads/{thread.pk}/messages/send/",
            {"text": "спам"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(MAX_UPLOAD_IMAGE_MB=0)
    def test_attachment_too_large_rejected(self):
        thread = Thread.objects.create(order=self.order, initiator=self.buyer)
        self.login(self.buyer)
        resp = self.client.post(
            f"/api/chat/threads/{thread.pk}/messages/send/",
            {"text": "фото", "attachment": self._png()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class ChatWSTestCase(TransactionTestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="ws-chat-seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="ws-chat-buyer@test.ru", password="Pass123!")
        self.stranger = User.objects.create_user(email="ws-chat-stranger@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин WS", city="Бишкек")
        self.category = Category.objects.create(name="Категория WS")
        self.order = _make_order(self.buyer, self.shop, self.category)
        self.thread = Thread.objects.create(order=self.order)

    @database_sync_to_async
    def _assert_db_state(self):
        self.assertEqual(Message.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.seller, title="Новое сообщение").exists())

    def _comm(self, path):
        return WebsocketCommunicator(application, path)

    async def test_message_broadcast_and_notification(self):
        buyer_ws = self._comm(f"/ws/chat/{self.thread.pk}/?token={AccessToken.for_user(self.buyer)}")
        seller_ws = self._comm(f"/ws/chat/{self.thread.pk}/?token={AccessToken.for_user(self.seller)}")
        seller_notifications = WebsocketCommunicator(
            application, f"/ws/notifications/?token={AccessToken.for_user(self.seller)}"
        )
        for comm in (buyer_ws, seller_ws, seller_notifications):
            connected, _ = await comm.connect()
            self.assertTrue(connected)

        await buyer_ws.send_json_to({"text": "Здравствуйте, есть в наличии?"})

        from_buyer = await buyer_ws.receive_json_from(timeout=5)
        from_seller = await seller_ws.receive_json_from(timeout=5)
        notification = await seller_notifications.receive_json_from(timeout=5)

        self.assertEqual(from_buyer["type"], "chat.message")
        self.assertEqual(from_seller["data"]["text"], "Здравствуйте, есть в наличии?")
        self.assertEqual(notification["type"], "notification")
        self.assertEqual(notification["data"]["type"], "chat.message")

        await self._assert_db_state()

        for comm in (buyer_ws, seller_ws, seller_notifications):
            await comm.disconnect()

    async def test_stranger_rejected(self):
        comm = self._comm(f"/ws/chat/{self.thread.pk}/?token={AccessToken.for_user(self.stranger)}")
        connected, code = await comm.connect()
        self.assertFalse(connected)

    async def test_empty_text_rejected_with_error(self):
        comm = self._comm(f"/ws/chat/{self.thread.pk}/?token={AccessToken.for_user(self.buyer)}")
        await comm.connect()
        await comm.send_json_to({"text": "   "})
        message = await comm.receive_json_from(timeout=5)
        self.assertEqual(message["type"], "error")
        await comm.disconnect()
