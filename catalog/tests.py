from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Brand, BrandStatus, Category, Product, Review
from core.models import Notification
from shops.models import Shop
from users.models import User


class CatalogTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Тест-магазин", city="Москва")
        self.category = Category.objects.create(name="Уход за лицом")
        self.subcategory = Category.objects.create(name="Кремы", parent=self.category)
        self.brand = Brand.objects.create(name="La Roche-Posay")
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.subcategory,
            brand=self.brand,
            name="Крем увлажняющий",
            price=Decimal("1000"),
            old_price=Decimal("1200"),
            stock=10,
        )

    def login(self, user):
        token = self.client.post("/api/auth/login/", {"email": user.email, "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_category_tree(self):
        resp = self.client.get("/api/categories/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [c["name"] for c in resp.data["results"]]
        self.assertIn("Уход за лицом", names)
        root = next(c for c in resp.data["results"] if c["name"] == "Уход за лицом")
        self.assertEqual(root["children"][0]["name"], "Кремы")

    def test_product_list_and_filter(self):
        resp = self.client.get(f"/api/products/?category={self.subcategory.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

        resp = self.client.get("/api/products/?price__lt=1100")
        self.assertEqual(resp.data["count"], 1)
        resp = self.client.get("/api/products/?price__lt=900")
        self.assertEqual(resp.data["count"], 0)

    def test_product_search(self):
        resp = self.client.get("/api/products/?q=крем")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_product_detail(self):
        resp = self.client.get(f"/api/products/{self.product.slug}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Крем увлажняющий")
        self.assertIn("shop", resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.views_count, 1)

    def test_review_requires_paid_order(self):
        self.login(self.buyer)
        resp = self.client.post(
            f"/api/products/{self.product.slug}/review/", {"rating": 5, "text": "Отлично"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Review.objects.exists())

    def test_favorites_toggle(self):
        self.login(self.buyer)
        resp = self.client.post(f"/api/favorites/toggle/{self.product.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["added"])
        resp = self.client.get("/api/favorites/")
        self.assertEqual(resp.data["count"], 1)
        resp = self.client.post(f"/api/favorites/toggle/{self.product.id}/")
        self.assertEqual(resp.data["added"], False)


class SellerBrandsTestCase(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="seller2@test.ru", password="Pass123!", is_seller=True)
        self.other_seller = User.objects.create_user(email="seller3@test.ru", password="Pass123!", is_seller=True)
        self.buyer = User.objects.create_user(email="buyer2@test.ru", password="Pass123!")
        self.shop = Shop.objects.create(owner=self.seller, name="Мой магазин", city="Москва")
        self.category = Category.objects.create(name="Уход за волосами")
        self.brand = Brand.objects.create(name="Matrix")

    def login(self, user):
        token = self.client.post("/api/auth/login/", {"email": user.email, "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_product(self, brand_id):
        return self.client.post(
            "/api/seller/products/",
            {
                "category": self.category.id,
                "brand": brand_id,
                "name": "Шампунь восстанавливающий",
                "price": "1500",
                "stock": 5,
            },
            format="json",
        )

    def test_seller_creates_brand_pending(self):
        self.login(self.seller)
        resp = self.client.post("/api/seller/brands/", {"name": "  Kerastase  "}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        brand = Brand.objects.get(name__iexact="Kerastase")
        self.assertEqual(brand.status, BrandStatus.PENDING)
        self.assertEqual(brand.created_by, self.seller)
        self.assertFalse(brand.is_active)
        self.assertTrue(Notification.objects.filter(user=self.seller).exists())

    def test_duplicate_brand_name_rejected(self):
        self.login(self.seller)
        resp = self.client.post("/api/seller/brands/", {"name": "matrix"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_seller_forbidden(self):
        self.login(self.buyer)
        resp = self.client.post("/api/seller/brands/", {"name": "Kerastase"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_brand_hidden_from_public_list(self):
        Brand.objects.create(name="SecretBrand", created_by=self.seller, status=BrandStatus.PENDING)
        resp = self.client.get("/api/brands/")
        names = [b["name"] for b in resp.data["results"]]
        self.assertIn("Matrix", names)
        self.assertNotIn("SecretBrand", names)

    def test_own_pending_brand_usable_in_product(self):
        pending = Brand.objects.create(name="MyPending", created_by=self.seller, status=BrandStatus.PENDING)
        self.login(self.seller)
        resp = self._create_product(pending.id)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_foreign_pending_and_rejected_brands_rejected_for_product(self):
        foreign_pending = Brand.objects.create(
            name="OtherPending", created_by=self.other_seller, status=BrandStatus.PENDING
        )
        rejected = Brand.objects.create(name="BadBrand", created_by=self.seller, status=BrandStatus.REJECTED)
        self.login(self.seller)
        resp = self._create_product(foreign_pending.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self._create_product(rejected.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
