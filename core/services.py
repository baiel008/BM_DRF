from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from .models import Notification


def _push(user_id, payload):
    """Кладёт событие в личную группу пользователя (если channel layer настроен)."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(f"user_{user_id}", payload)


def notify(user, type, title, text="", link="", email=False):
    """Единая точка отправки уведомлений: сохранить в БД + доставить по WebSocket.

    Офлайн-пользователь получит уведомление через REST-список при следующем входе.
    email=True — продублировать письмом (если NOTIFICATION_EMAIL_ENABLED).
    """
    notification = Notification.objects.create(user=user, title=title, text=text, link=link)
    _push(
        user.pk,
        {
            "type": "notification",
            "data": {
                "id": notification.pk,
                "type": type,
                "title": title,
                "text": text,
                "link": link,
                "created_at": notification.created_at.isoformat(),
            },
        },
    )
    if email and settings.NOTIFICATION_EMAIL_ENABLED:
        _queue_email(user.pk, title, f"{text}\n\n{link}".strip())
    return notification


def _queue_email(user_id, subject, body):
    from .tasks import send_notification_email

    try:
        send_notification_email.delay(user_id, subject, body)
    except Exception:
        # Брокер недоступен — шлём синхронно, чтобы не терять письмо
        try:
            send_notification_email(user_id, subject, body)
        except Exception:
            pass
