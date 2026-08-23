from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product
from core.models import Notification
from finance.models import Commission, SellerWallet
from orders.models import Order, OrderItem, PaymentMethod
from shops.models import Shop
from users.models import User

from .models import Payment, PaymentStatus
from .services import PaymentService


def make_order_with_payment(buyer, shop, category, amount=Decimal("1000"), method=PaymentMethod.CARD):
    product = Product.objects.create(
        shop=shop, category=category, name="Крем", price=amount, stock=10
    )
    order = Order.objects.create(
        user=buyer,
        payment_method=method,
        recipient_name="Иван",
        phone="+7 999 000-00-00",
        address="ул. Ленина 1",
        total=amount,
    )
    OrderItem.objects.create(
        order=order, product=product, shop=shop,
        product_name=product.name, price=amount, quantity=1, subtotal=amount,
    )
    payment = Payment.objects.create(order=order, user=buyer, amount=amount, method=method)
    return order, payment


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
class WebhookTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин", city="Москва")
        self.category = Category.objects.create(name="Категория")
        self.order, self.payment = make_order_with_payment(self.buyer, self.shop, self.category)

    def _post_webhook(self, event):
        with patch("payments.providers.StripeProvider.verify_webhook", return_value=event):
            return self.client.post("/api/payments/webhook/stripe/", {}, format="json")

    def test_checkout_session_completed_confirms_payment(self):
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"payment_id": self.payment.pk}, "payment_intent": "pi_123"}},
        }
        resp = self._post_webhook(event)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(self.payment.provider_payment_id, "pi_123")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")
        wallet = SellerWallet.objects.get(shop=self.shop)
        self.assertEqual(wallet.available, Decimal("900.00"))

    def test_payment_intent_succeeded_confirms_payment(self):
        self.payment.provider_payment_id = "pi_456"
        self.payment.save(update_fields=["provider_payment_id"])
        event = {"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_456"}}}
        resp = self._post_webhook(event)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCEEDED)

    def test_invalid_signature_returns_403(self):
        with patch(
            "payments.providers.StripeProvider.verify_webhook",
            side_effect=PermissionError("Invalid signature"),
        ):
            resp = self.client.post("/api/payments/webhook/stripe/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_event_ignored(self):
        resp = self._post_webhook({"type": "invoice.paid", "data": {"object": {}}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class RefundTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller2@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer2@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин 2", city="Москва")
        self.category = Category.objects.create(name="Категория 2")
        self.order, self.payment = make_order_with_payment(self.buyer, self.shop, self.category)
        PaymentService.confirm_payment(self.payment)

    def test_partial_refund_recalculates_wallet_proportionally(self):
        PaymentService.refund(self.payment, Decimal("400"))
        wallet = SellerWallet.objects.get(shop=self.shop)
        # было: available 900 (1000 − комиссия 10%); вернули 400 → доход 600, комиссия 60 → доступно 540
        self.assertEqual(wallet.available, Decimal("540.00"))
        self.assertEqual(wallet.total_earned, Decimal("600.00"))
        commission = Commission.objects.get(order=self.order)
        self.assertEqual(commission.shop_subtotal, Decimal("600.00"))
        self.assertEqual(commission.amount, Decimal("60.00"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PARTIALLY_REFUNDED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")

    def test_full_refund_reverses_wallet_and_cancels_order(self):
        PaymentService.refund(self.payment)
        wallet = SellerWallet.objects.get(shop=self.shop)
        self.assertEqual(wallet.available, Decimal("0.00"))
        self.assertEqual(wallet.total_earned, Decimal("0.00"))
        self.assertFalse(Commission.objects.filter(order=self.order).exists())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.REFUNDED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")


class CashConfirmTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller3@test.ru", password="Pass123!", is_seller=True)
        self.other_seller = User.objects.create_user(email="seller4@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer3@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин 3", city="Бишкек")
        self.category = Category.objects.create(name="Категория 3")
        self.order, self.payment = make_order_with_payment(
            self.buyer, self.shop, self.category, method=PaymentMethod.CASH
        )

    def login(self, user):
        token = self.client.post("/api/auth/login/", {"email": user.email, "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_seller_confirms_cash_payment(self):
        self.login(self.seller)
        resp = self.client.post(f"/api/payments/{self.order.pk}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCEEDED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")
        self.assertTrue(Notification.objects.filter(user=self.buyer, title="Оплата получена").exists())

    def test_unrelated_seller_forbidden(self):
        self.login(self.other_seller)
        resp = self.client.post(f"/api/payments/{self.order.pk}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_card_payment_cannot_be_manually_confirmed(self):
        order, payment = make_order_with_payment(
            self.buyer, self.shop, self.category, method=PaymentMethod.CARD
        )
        self.login(self.seller)
        resp = self.client.post(f"/api/payments/{order.pk}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_double_confirm_returns_already_paid(self):
        PaymentService.confirm_payment(self.payment)
        self.login(self.seller)
        resp = self.client.post(f"/api/payments/{self.order.pk}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["already_paid"])
