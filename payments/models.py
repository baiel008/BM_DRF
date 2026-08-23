from django.conf import settings
from django.db import models


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Ожидает оплаты"
    PROCESSING = "processing", "Обрабатывается"
    SUCCEEDED = "succeeded", "Оплачен"
    FAILED = "failed", "Ошибка"
    CANCELED = "canceled", "Отменён"
    REFUNDED = "refunded", "Возвращён"
    PARTIALLY_REFUNDED = "partially_refunded", "Частично возвращён"


class Payment(models.Model):
    """Платёж по заказу. Создаётся вместе с заказом, затем идёт в провайдера."""

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="payment", verbose_name="Заказ"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments", verbose_name="Покупатель"
    )
    provider = models.CharField("Провайдер", max_length=30, default="stripe")
    provider_payment_id = models.CharField("ID в платёжной системе", max_length=255, unique=True, null=True, blank=True)
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    currency = models.CharField("Валюта", max_length=3, default="kgs")
    status = models.CharField("Статус", max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    method = models.CharField("Способ", max_length=10, default="card")
    redirect_url = models.CharField("Ссылка на оплату", max_length=500, blank=True)
    paid_at = models.DateTimeField("Оплачен", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.order.number}: {self.amount} сом ({self.status})"

    @property
    def is_paid(self):
        return self.status == PaymentStatus.SUCCEEDED
