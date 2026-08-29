from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order, OrderItem, PaymentMethod, OrderStatus
from payments.models import Payment
from users.models import User

PUBLIC = "/api/stats/users/"
UNLOCK = "/api/staff/analytics/unlock/"
SUMMARY = "/api/staff/analytics/summary/"
PIN = "926411"


@override_settings(ANALYTICS_PASSWORD=PIN, ANALYTICS_TIMEOUT_SECONDS=15)
class AnalyticsTestCase(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(email="buy@test.ru", password="Pass123!")
        self.seller = User.objects.create_user(email="sell@test.ru", password="Pass123!", is_seller=True)
        # оплаченный заказ: 2 шт по 1000
        order = Order.objects.create(
            user=self.buyer,
            payment_method=PaymentMethod.CARD,
            recipient_name="Иван", phone="+996", address="Бишкек",
            total=Decimal("2000"),
        )
        from catalog.models import Category, Product
        from shops.models import Shop

        shop = Shop.objects.create(owner=self.seller, name="Маг", city="Бишкек")
        cat = Category.objects.create(name="Крем")
        product = Product.objects.create(shop=shop, category=cat, name="Крем", price=Decimal("1000"), stock=5)
        OrderItem.objects.create(
            order=order, product=product, shop=shop, product_name="Крем",
            price=Decimal("1000"), quantity=2, subtotal=Decimal("2000"),
        )
        Payment.objects.create(
            order=order, user=self.buyer, status="succeeded", method="stripe", amount=Decimal("2000")
        )
        # ещё один неоплаченный заказ — в аналитику не попадает
        order2 = Order.objects.create(
            user=self.buyer, payment_method=PaymentMethod.CASH,
            recipient_name="Иван", phone="+996", address="Бишкек", total=Decimal("500"),
        )
        OrderItem.objects.create(
            order=order2, product=product, shop=shop, product_name="Крем",
            price=Decimal("500"), quantity=1, subtotal=Decimal("500"),
        )

    def test_public_stats_accessible_without_pin(self):
        resp = self.client.get(PUBLIC)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_users"], 2)  # buyer + seller
        self.assertNotIn("gmv", resp.data)

    def test_unlock_wrong_pin_rejected(self):
        resp = self.client.post(UNLOCK, {"pin": "000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_summary_requires_pin(self):
        resp = self.client.get(SUMMARY)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unlock_then_summary(self):
        resp = self.client.post(UNLOCK, {"pin": PIN}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = resp.data["token"]
        resp = self.client.get(SUMMARY, HTTP_X_ANALYTICS_TOKEN=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertEqual(data["users"]["total"], 2)
        self.assertEqual(data["users"]["sellers"], 1)
        self.assertEqual(data["sales"]["orders_paid"], 1)
        self.assertEqual(data["sales"]["units_sold"], 2)
        self.assertEqual(data["sales"]["gmv"], 2000.0)
        # комиссия платформы 10%
        self.assertEqual(data["sales"]["platform_commission"], 200.0)

    def test_bad_token_rejected(self):
        resp = self.client.get(SUMMARY, HTTP_X_ANALYTICS_TOKEN="wrong")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(ANALYTICS_PASSWORD=PIN, ANALYTICS_TIMEOUT_SECONDS=0)
class AnalyticsExpiredSessionTestCase(APITestCase):
    def test_expired_session_rejected(self):
        resp = self.client.post(UNLOCK, {"pin": PIN}, format="json")
        token = resp.data["token"]
        resp = self.client.get(SUMMARY, HTTP_X_ANALYTICS_TOKEN=token)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
