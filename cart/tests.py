from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Brand, Category, Product
from orders.models import Order
from payments.models import Payment
from payments.services import PaymentService
from finance.models import Commission, SellerWallet
from shops.models import Shop
from users.models import User


class MarketFlowTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Тест-магазин", city="Москва")
        self.category = Category.objects.create(name="Уход за лицом")
        self.brand = Brand.objects.create(name="Vichy")
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            brand=self.brand,
            name="Сыворотка",
            price=Decimal("1000"),
            stock=10,
        )
        token = self.client.post("/api/auth/login/", {"email": "buyer@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def login_seller(self):
        token = self.client.post("/api/auth/login/", {"email": "seller@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_full_purchase_flow(self):
        # корзина
        resp = self.client.post("/api/cart/add/", {"product_id": self.product.id, "quantity": 2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        resp = self.client.get("/api/cart/")
        self.assertEqual(resp.data["count"], 2)
        self.assertEqual(resp.data["total"], 2000.0)

        # заказ
        resp = self.client.post(
            "/api/checkout/",
            {"recipient_name": "Мария", "phone": "+7 900 111 22 33", "address": "Москва", "payment_method": "card"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=resp.data["id"])
        self.assertEqual(order.status, "new")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

        # платёж и подтверждение
        resp = self.client.post(f"/api/payments/{order.id}/create/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payment = Payment.objects.get(order=order)
        PaymentService.confirm_payment(payment)

        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payment.status, "succeeded")
        self.assertEqual(order.status, "paid")

        # комиссия и кошелёк
        commission = Commission.objects.get(order=order)
        self.assertEqual(commission.amount, Decimal("200.00"))
        wallet = SellerWallet.objects.get(shop=self.shop)
        self.assertEqual(wallet.total_earned, Decimal("2000.00"))
        self.assertEqual(wallet.available, Decimal("1800.00"))

    def test_cart_requires_auth(self):
        self.client.credentials()
        resp = self.client.get("/api/cart/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_checkout_empty_cart(self):
        resp = self.client.post(
            "/api/checkout/",
            {"recipient_name": "Мария", "phone": "+7 900 111 22 33", "address": "Москва", "payment_method": "card"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_dashboard(self):
        self.login_seller()
        resp = self.client.get("/api/seller/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["products_count"], 1)

    def test_seller_sees_only_own_orders(self):
        self.client.post("/api/cart/add/", {"product_id": self.product.id, "quantity": 1}, format="json")
        self.client.post(
            "/api/checkout/",
            {"recipient_name": "Мария", "phone": "+7 900 111 22 33", "address": "Москва", "payment_method": "card"},
            format="json",
        )
        self.login_seller()
        resp = self.client.get("/api/seller/orders/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_payout_reduces_wallet(self):
        self.client.post("/api/cart/add/", {"product_id": self.product.id, "quantity": 1}, format="json")
        order_id = self.client.post(
            "/api/checkout/",
            {"recipient_name": "Мария", "phone": "+7 900 111 22 33", "address": "Москва", "payment_method": "card"},
            format="json",
        ).data["id"]
        payment = Payment.objects.get(order_id=order_id)
        PaymentService.confirm_payment(payment)

        self.login_seller()
        resp = self.client.post("/api/finance/payouts/", {"amount": 400}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        wallet = SellerWallet.objects.get(shop=self.shop)
        self.assertEqual(wallet.available, Decimal("500.00"))
