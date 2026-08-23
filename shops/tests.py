from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Brand, Category, Product
from shops.models import Shop
from users.models import User


class ShopTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Тест-магазин", city="Москва")
        self.category = Category.objects.create(name="Уход за лицом")
        self.brand = Brand.objects.create(name="Nivea")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, brand=self.brand, name="Крем", price=Decimal("500"), stock=5
        )

    def login_buyer(self):
        token = self.client.post("/api/auth/login/", {"email": "buyer@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_shop_list_and_detail(self):
        resp = self.client.get("/api/shops/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        resp = self.client.get(f"/api/shops/{self.shop.slug}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Тест-магазин")

    def test_seller_can_update_own_shop(self):
        token = self.client.post("/api/auth/login/", {"email": "seller@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.patch(f"/api/seller/shop/", {"description": "Новое описание"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.description, "Новое описание")

    def test_buyer_cannot_edit_shop(self):
        self.login_buyer()
        resp = self.client.patch(f"/api/seller/shop/", {"description": "Взлом"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_follow_shop(self):
        self.login_buyer()
        resp = self.client.post(f"/api/follows/toggle/{self.shop.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["following"])
        resp = self.client.get("/api/followed-shops/")
        self.assertEqual(resp.data["count"], 1)
        # отписка
        resp = self.client.post(f"/api/follows/toggle/{self.shop.id}/")
        self.assertFalse(resp.data["following"])
