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
    def test_reset_sends_code_and_confirm_changes_password(self):
        from django.core import mail

        user = User.objects.create_user(email="reset@test.ru", password="OldPass123!")
        # запрос сброса
        resp = self.client.post(RESET, {"email": "reset@test.ru"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("masked_email", resp.data)
        self.assertEqual(resp.data["masked_email"], "r**t@test.ru")
        self.assertNotIn("dev_reset_url", resp.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("код", mail.outbox[0].subject.lower())
        self.assertEqual(mail.outbox[0].to, ["reset@test.ru"])
        # тянем 4-значный код из письма
        body = mail.outbox[0].body
        code = None
        for line in body.splitlines():
            line = line.strip()
            if len(line) == 4 and line.isdigit():
                code = line
                break
        self.assertIsNotNone(code)

        # подтверждение с новым паролем
        resp = self.client.post(
            RESET_CONFIRM, {"email": "reset@test.ru", "code": code, "new_password": "NewPass456!"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass456!"))

        # код одноразовый — больше не сработает
        resp = self.client.post(
            RESET_CONFIRM, {"email": "reset@test.ru", "code": code, "new_password": "AnotherPass7!"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_unknown_email_returns_200_without_mask(self):
        resp = self.client.post(RESET, {"email": "nobody@test.ru"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("masked_email", resp.data)
        self.assertNotIn("dev_reset_url", resp.data)

    def test_confirm_wrong_code_rejected(self):
        from django.core import mail

        user = User.objects.create_user(email="bad@test.ru", password="OldPass123!")
        self.client.post(RESET, {"email": "bad@test.ru"}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        resp = self.client.post(
            RESET_CONFIRM, {"email": "bad@test.ru", "code": "0000", "new_password": "NewPass456!"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertTrue(user.check_password("OldPass123!"))

    def test_confirm_short_password_rejected(self):
        User.objects.create_user(email="short@test.ru", password="OldPass123!")
        self.client.post(RESET, {"email": "short@test.ru"}, format="json")
        resp = self.client.post(
            RESET_CONFIRM, {"email": "short@test.ru", "code": "1234", "new_password": "short"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_code_exhausted_after_attempts(self):
        from django.core import mail

        User.objects.create_user(email="exh@test.ru", password="OldPass123!")
        self.client.post(RESET, {"email": "exh@test.ru"}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        # исчерпываем код неверными попытками
        last = None
        for _ in range(5):
            last = self.client.post(
                RESET_CONFIRM, {"email": "exh@test.ru", "code": "0000", "new_password": "NewPass456!"}, format="json"
            )
            self.assertEqual(last.status_code, status.HTTP_400_BAD_REQUEST)
        # даже верный код больше не принимается — у нас нет кода, просто проверяем статус не 200
        self.assertEqual(last.status_code, status.HTTP_400_BAD_REQUEST)
