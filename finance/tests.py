from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from finance.models import Payout, PayoutStatus, SellerWallet, Transaction
from finance.services import WalletService
from shops.models import Shop
from users.models import User


class PayoutTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@test.ru", password="Pass123!", is_staff=True, is_superuser=True
        )
        self.seller = User.objects.create_user(email="seller@test.ru", password="Pass123!", is_seller=True)
        self.shop = Shop.objects.create(owner=self.seller, name="Магазин", city="Москва")
        self.wallet = SellerWallet.objects.create(shop=self.shop, available=Decimal("500"), total_earned=Decimal("500"))

    def login(self, user):
        token = self.client.post("/api/auth/login/", {"email": user.email, "password": "Pass123!"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_seller_requests_payout(self):
        self.login(self.seller)
        resp = self.client.post("/api/finance/payouts/", {"amount": 200}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available, Decimal("300.00"))
        payout = Payout.objects.get(pk=resp.data["id"])
        self.assertEqual(payout.status, PayoutStatus.PENDING)

    def test_payout_more_than_available_rejected(self):
        self.login(self.seller)
        resp = self.client.post("/api/finance/payouts/", {"amount": 9999}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_marks_payout_succeeded(self):
        payout = WalletService.request_payout(self.shop, Decimal("200"))
        self.login(self.admin)
        resp = self.client.post(
            f"/api/finance/payouts/{payout.pk}/mark/",
            {"status": "succeeded", "provider_payout_id": "tr_1"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payout.refresh_from_db()
        self.assertEqual(payout.status, PayoutStatus.SUCCEEDED)
        self.assertEqual(payout.provider_payout_id, "tr_1")
        self.assertIsNotNone(payout.completed_at)

    def test_failed_payout_returns_money_to_wallet(self):
        payout = WalletService.request_payout(self.shop, Decimal("200"))
        self.login(self.admin)
        resp = self.client.post(f"/api/finance/payouts/{payout.pk}/mark/", {"status": "failed"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available, Decimal("500.00"))
        self.assertTrue(Transaction.objects.filter(payout=payout).count() >= 2)

    def test_non_admin_cannot_mark_payout(self):
        payout = WalletService.request_payout(self.shop, Decimal("200"))
        self.login(self.seller)
        resp = self.client.post(f"/api/finance/payouts/{payout.pk}/mark/", {"status": "succeeded"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
