from django.conf import settings
from django.core.mail import send_mail

from config.celery import app


@app.task(name="core.send_notification_email")
def send_notification_email(user_id, subject, body):
    """Email-дубль уведомления. Отправка асинхронная (Celery worker)."""
    from users.models import User

    user = User.objects.filter(pk=user_id, is_active=True).first()
    if not user:
        return
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
