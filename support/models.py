from django.conf import settings
from django.db import models


class TicketStatus(models.TextChoices):
    OPEN = "open", "Открыт"
    IN_PROGRESS = "in_progress", "В работе"
    RESOLVED = "resolved", "Решён"
    CLOSED = "closed", "Закрыт"


class TicketPriority(models.TextChoices):
    LOW = "low", "Низкий"
    NORMAL = "normal", "Обычный"
    HIGH = "high", "Высокий"


class SupportTicket(models.Model):
    """Обращение в техподдержку."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="support_tickets", verbose_name="Автор",
    )
    subject = models.CharField("Тема", max_length=200)
    description = models.TextField("Описание")
    status = models.CharField(
        "Статус", max_length=20, choices=TicketStatus.choices,
        default=TicketStatus.OPEN, db_index=True,
    )
    priority = models.CharField(
        "Приоритет", max_length=10, choices=TicketPriority.choices,
        default=TicketPriority.NORMAL,
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_tickets", verbose_name="Оператор",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Обращение"
        verbose_name_plural = "Обращения"
        ordering = ("-updated_at",)

    def __str__(self):
        return f"#{self.pk} {self.subject} ({self.status})"

    def has_access(self, user):
        return user.is_staff or self.user_id == user.id


class SupportMessage(models.Model):
    """Сообщение в тикете: автор тикета или оператор."""

    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages", verbose_name="Обращение"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="support_messages", verbose_name="Автор",
    )
    text = models.TextField("Текст")
    attachment = models.ImageField("Вложение", upload_to="support/%Y/%m/", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение поддержки"
        verbose_name_plural = "Сообщения поддержки"
        ordering = ("created_at",)

    def __str__(self):
        return f"Тикет #{self.ticket_id}: {self.text[:30]}"
