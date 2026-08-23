from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Notification
from users.models import User

TICKETS = "/api/support/tickets/"


def _auth(client, user):
    resp = client.post(
        "/api/auth/login/", {"email": user.email, "password": "Pass123!"}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")


class SupportTestCase(APITestCase):
    def setUp(self):
        # Лимиты запросов живут в кэше между тестами — сбрасываем
        cache.clear()
        self.user = User.objects.create_user(email="u@test.ru", password="Pass123!")
        self.other = User.objects.create_user(email="o@test.ru", password="Pass123!")
        self.staff = User.objects.create_user(
            email="staff@test.ru", password="Pass123!", is_staff=True
        )

    def _create_ticket(self, client=None, subject="Не пришёл заказ 12345"):
        client = client or self.client
        return client.post(
            TICKETS,
            {"subject": subject, "description": "Опишите проблему подробнее здесь"},
            format="json",
        )

    def test_create_ticket(self):
        _auth(self.client, self.user)
        resp = self._create_ticket()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "open")
        # Уведомление операторам о новом тикете не требуется по ТЗ (план), но тикет создан от автора
        from support.models import SupportTicket

        ticket = SupportTicket.objects.get(pk=resp.data["id"])
        self.assertEqual(ticket.user, self.user)

    def test_list_shows_only_own_tickets(self):
        _auth(self.client, self.user)
        self._create_ticket()
        _auth(self.client, self.other)
        resp = self.client.get(TICKETS)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)

    def test_staff_sees_all_tickets(self):
        _auth(self.client, self.user)
        self._create_ticket()
        _auth(self.client, self.staff)
        resp = self.client.get(TICKETS + "?status=open")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_detail_access_control(self):
        _auth(self.client, self.user)
        ticket_id = self._create_ticket().data["id"]
        detail = f"{TICKETS}{ticket_id}/"
        # Автор видит
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_200_OK)
        # Чужой пользователь — нет
        _auth(self.client, self.other)
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_403_FORBIDDEN)
        # Оператор видит
        _auth(self.client, self.staff)
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_200_OK)

    def test_staff_reply_notifies_author_and_sets_in_progress(self):
        _auth(self.client, self.user)
        ticket_id = self._create_ticket().data["id"]
        url = f"{TICKETS}{ticket_id}/messages/"
        before = Notification.objects.count()
        _auth(self.client, self.staff)
        resp = self.client.post(url, {"text": "Проверяем ваш заказ, ответим в течение часа"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["is_from_staff"])
        # Статус стал in_progress
        detail = self.client.get(f"{TICKETS}{ticket_id}/").data
        self.assertEqual(detail["status"], "in_progress")
        # Автор получил уведомление support.reply
        notification = Notification.objects.filter(user=self.user).order_by("id").last()
        self.assertIsNotNone(notification)
        self.assertIn("поддержки", notification.title)

    def test_closed_ticket_rejects_messages(self):
        from support.models import SupportTicket

        _auth(self.client, self.user)
        ticket_id = self._create_ticket().data["id"]
        SupportTicket.objects.filter(pk=ticket_id).update(status="closed")
        _auth(self.client, self.staff)
        resp = self.client.post(
            f"{TICKETS}{ticket_id}/messages/", {"text": "Сообщение"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_staff_can_update_status(self):
        _auth(self.client, self.user)
        ticket_id = self._create_ticket().data["id"]
        update_url = f"{TICKETS}{ticket_id}/update/"
        # Обычному пользователю нельзя
        resp = self.client.patch(update_url, {"status": "resolved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # Оператору можно; resolve → уведомление автору
        _auth(self.client, self.staff)
        resp = self.client.patch(update_url, {"status": "resolved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "resolved")

    def test_assignee_must_be_staff(self):
        _auth(self.client, self.staff)
        ticket_id = self._create_ticket(self.client).data["id"]
        resp = self.client.patch(
            f"{TICKETS}{ticket_id}/update/",
            {"assignee": self.other.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_short_subject(self):
        _auth(self.client, self.user)
        resp = self._create_ticket(subject="ок")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(TICKETS).status_code, status.HTTP_401_UNAUTHORIZED)

    # ─── Вложения и email-дубли ─────────────────────────────────────────────────

    def _png(self):
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = BytesIO()
        Image.new("RGB", (10, 10), "blue").save(buf, format="PNG")
        return SimpleUploadedFile("shot.png", buf.getvalue(), content_type="image/png")

    def test_message_with_attachment(self):
        _auth(self.client, self.user)
        ticket_id = self._create_ticket().data["id"]
        resp = self.client.post(
            f"{TICKETS}{ticket_id}/messages/",
            {"text": "Скриншот ошибки", "attachment": self._png()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["attachment"])

    def test_email_duplicate_on_staff_reply(self):
        from django.core import mail
        from django.test import override_settings

        with override_settings(NOTIFICATION_EMAIL_ENABLED=True):
            _auth(self.client, self.user)
            ticket_id = self._create_ticket().data["id"]
            _auth(self.client, self.staff)
            resp = self.client.post(
                f"{TICKETS}{ticket_id}/messages/", {"text": "Ответ поддержки"}, format="json"
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Celery в тестах eager → письмо ушло сразу
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
