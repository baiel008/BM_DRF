from django.conf import settings
from django.db import models


class AnalyticsSession(models.Model):
    """Короткоживущая сессия доступа к аналитике после ввода PIN.

    Создаётся при верном PIN, живёт до ANALYTICS_TIMEOUT_SECONDS бездействия.
    Любой GET summary продлевает last_seen.
    """

    token = models.CharField("Токен", max_length=64, unique=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    last_seen = models.DateTimeField("Активна до", auto_now=True)

    class Meta:
        verbose_name = "PIN-сессия аналитики"
        verbose_name_plural = "PIN-сессии аналитики"

    @property
    def is_active(self):
        from django.utils import timezone

        return (timezone.now() - self.last_seen).total_seconds() < settings.ANALYTICS_TIMEOUT_SECONDS
