from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User

REGISTER_BUYER = "/api/auth/register/buyer/"
REGISTER_SELLER = "/api/auth/register/seller/"
LOGIN = "/api/auth/login/"
ME = "/api/me/"


class AuthTestCase(APITestCase):
    def test_register_buyer(self):
        resp = self.client.post(
            REGISTER_BUYER,
            {"email": "buyer@test.ru", "password": "TestPass123!", "first_name": "Иван", "last_name": "Петров"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        user = User.objects.get(email="buyer@test.ru")
        self.assertFalse(user.is_seller)

    def test_register_seller(self):
        resp = self.client.post(
            REGISTER_SELLER,
            {"email": "seller@test.ru", "password": "TestPass123!", "first_name": "Анна"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(email="seller@test.ru").is_seller)

    def test_login_and_me(self):
        User.objects.create_user(email="a@test.ru", password="Pass123!")
        resp = self.client.post(LOGIN, {"email": "a@test.ru", "password": "Pass123!"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        me = self.client.get(ME)
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["email"], "a@test.ru")
        self.assertIn("is_seller", me.data)

    def test_duplicate_email_registration(self):
        User.objects.create_user(email="dup@test.ru", password="Pass123!")
        resp = self.client.post(REGISTER_BUYER, {"email": "dup@test.ru", "password": "Pass123!"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
