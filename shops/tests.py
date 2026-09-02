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

    def login_seller(self):
        token = self.client.post("/api/auth/login/", {"email": "seller@test.ru", "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_product(self, **kwargs):
        self.login_seller()
        payload = {
            "category": self.category.id,
            "brand": self.brand.id,
            "name": "Крем для рук",
            "price": "700",
            "stock": "10",
        }
        payload.update(kwargs)
        return self.client.post("/api/seller/products/", payload, format="json")

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

    def test_create_product_auto_sku(self):
        resp = self._create_product()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data["sku"])
        self.assertRegex(resp.data["sku"], r"^BM-[0-9A-F]{8}$")

    def test_create_product_wholesale_requires_both_fields(self):
        resp = self._create_product(wholesale_price="600")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self._create_product(wholesale_min_qty="10")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self._create_product(wholesale_price="600", wholesale_min_qty="10")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_product_multilang_fields(self):
        resp = self._create_product(
            name_ru="Крем",
            name_ky="Крем кыргызча",
            name_en="Cream",
            description_ru="Описание",
            description_en="Description",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["name_ru"], "Крем")
        self.assertEqual(resp.data["name_ky"], "Крем кыргызча")
        self.assertEqual(resp.data["name_en"], "Cream")

    def test_brand_resolve_creates_new(self):
        self.login_seller()
        resp = self.client.post("/api/seller/brands/resolve/", {"name": "Lancome"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "pending")
        # повторный вызов возвращает тот же бренд
        resp2 = self.client.post("/api/seller/brands/resolve/", {"name": "lancome"}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["id"], resp.data["id"])

    def test_upload_product_image(self):
        import tempfile
        from PIL import Image as PILImage

        self.login_seller()
        resp = self._create_product()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pid = resp.data["id"]

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            PILImage.new("RGB", (10, 10), "red").save(tmp.name, format="PNG")
            with open(tmp.name, "rb") as f:
                up = self.client.post(
                    f"/api/seller/products/{pid}/images/",
                    {"image": f, "is_main": "true"},
                    format="multipart",
                )
        self.assertEqual(up.status_code, status.HTTP_201_CREATED, up.data)
        self.assertIn("url", up.data)
        self.assertEqual(Product.objects.get(pk=pid).images.count(), 1)
