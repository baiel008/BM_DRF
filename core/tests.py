from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Brand, Category, Product
from core.models import Notification
from orders.models import Order, OrderItem
from payments.models import Payment
from payments.services import PaymentService
from shops.models import Shop
from users.models import User


class NotificationTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин", city="Москва")
        self.category = Category.objects.create(name="Категория")
        self.brand = Brand.objects.create(name="Бренд")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, brand=self.brand, name="Товар", price=Decimal("1000"), stock=5
        )

    def test_notifications_on_new_order(self):
        token = self.client.post("/api/auth/login/", {"email": "buyer@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.client.post("/api/cart/add/", {"product_id": self.product.id, "quantity": 1}, format="json")
        self.client.post(
            "/api/checkout/",
            {"recipient_name": "Б", "phone": "+7 900 000 00 00", "address": "Москва", "payment_method": "card"},
            format="json",
        )
        # продавец получил уведомление о новом заказе
        self.assertTrue(Notification.objects.filter(user=self.seller).exists())

        seller_token = self.client.post("/api/auth/login/", {"email": "seller@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {seller_token}")
        resp = self.client.get("/api/notifications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertIn("заказ", resp.data["results"][0]["text"])

        resp = self.client.post("/api/notifications/mark-all-read/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(user=self.seller, is_read=False).exists())

    def test_unread_count_and_mark_single_read(self):
        Notification.objects.create(user=self.buyer, title="Первое")
        Notification.objects.create(user=self.buyer, title="Второе")

        token = self.client.post("/api/auth/login/", {"email": "buyer@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        resp = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 2)

        notification_id = Notification.objects.get(user=self.buyer, title="Первое").pk
        resp = self.client.post(f"/api/notifications/{notification_id}/read/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["unread_count"], 1)

        resp = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(resp.data["count"], 1)

    def test_cannot_read_foreign_notification(self):
        notification = Notification.objects.create(user=self.seller, title="Продавцу")
        token = self.client.post("/api/auth/login/", {"email": "buyer@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.post(f"/api/notifications/{notification.pk}/read/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class OrderTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин", city="Москва")
        self.category = Category.objects.create(name="Категория")
        self.brand = Brand.objects.create(name="Бренд")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, brand=self.brand, name="Товар", price=Decimal("1000"), stock=5
        )
        self.token = self.client.post("/api/auth/login/", {"email": "buyer@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def create_order(self):
        self.client.post("/api/cart/add/", {"product_id": self.product.id, "quantity": 2}, format="json")
        return self.client.post(
            "/api/checkout/",
            {"recipient_name": "Б", "phone": "+7 900 000 00 00", "address": "Москва", "payment_method": "card"},
            format="json",
        ).data["id"]

    def test_order_status_transitions(self):
        order_id = self.create_order()
        # продавец подтверждает заказ
        seller_token = self.client.post("/api/auth/login/", {"email": "seller@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {seller_token}")
        resp = self.client.post(f"/api/seller/orders/{order_id}/status/", {"status": "accepted"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, "accepted")

    def test_seller_cannot_touch_other_orders(self):
        other_seller = User.objects.create_user(email="other@test.ru", password="Pass123!", is_seller=True)
        Shop.objects.create(owner=other_seller, name="Чужой", city="Москва")
        order_id = self.create_order()
        other_token = self.client.post("/api/auth/login/", {"email": "other@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token}")
        resp = self.client.post(f"/api/seller/orders/{order_id}/status/", {"status": "accepted"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_refund_returns_money_to_wallet(self):
        from finance.models import Commission, SellerWallet

        order_id = self.create_order()
        payment = Payment.objects.get(order_id=order_id)
        PaymentService.confirm_payment(payment)
        wallet_before = SellerWallet.objects.get(shop=self.shop).available
        commission_before = Commission.objects.filter(order_id=order_id).count()

        PaymentService.refund(payment)

        order = Order.objects.get(pk=order_id)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "refunded")
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(Commission.objects.filter(order_id=order_id).count(), 0)
        self.assertEqual(Commission.objects.filter(order_id=order_id).count(), commission_before - 1)
        self.assertEqual(SellerWallet.objects.get(shop=self.shop).available, wallet_before - Decimal("1800.00"))

    def test_order_items_reduce_stock(self):
        self.create_order()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
