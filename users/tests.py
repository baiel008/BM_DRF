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


RESET = "/api/auth/password/reset/"
RESET_CONFIRM = "/api/auth/password/reset/confirm/"


class PasswordResetTestCase(APITestCase):
    def test_reset_sends_mail_and_confirm_changes_password(self):
        from django.core import mail

        user = User.objects.create_user(email="reset@test.ru", password="OldPass123!")
        # запрос сброса
        resp = self.client.post(RESET, {"email": "reset@test.ru"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("сброс", mail.outbox[0].subject.lower())
        self.assertEqual(mail.outbox[0].to, ["reset@test.ru"])
        # тянем token из письма
        body = mail.outbox[0].body
        token = body.split("token=")[1].split()[0]

        # подтверждение с новым паролем
        resp = self.client.post(
            RESET_CONFIRM, {"email": "reset@test.ru", "token": token, "new_password": "NewPass456!"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass456!"))

        # старый токен одноразовый — больше не сработает
        resp = self.client.post(
            RESET_CONFIRM, {"email": "reset@test.ru", "token": token, "new_password": "AnotherPass7!"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_unknown_email_returns_200(self):
        resp = self.client.post(RESET, {"email": "nobody@test.ru"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_confirm_invalid_token_rejected(self):
        resp = self.client.post(
            RESET_CONFIRM, {"email": "a@b.ru", "token": "garbage", "new_password": "NewPass456!"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_short_password_rejected(self):
        User.objects.create_user(email="short@test.ru", password="OldPass123!")
        self.client.post(RESET, {"email": "short@test.ru"}, format="json")
        resp = self.client.post(
            RESET_CONFIRM, {"email": "short@test.ru", "token": "x", "new_password": "short"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
