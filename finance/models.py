from django.db import models


class CommissionRule(models.Model):
    """Правило комиссии: глобальное (shop=null) или для конкретного магазина."""

    shop = models.OneToOneField(
        "shops.Shop", on_delete=models.CASCADE, related_name="commission_rule", null=True, blank=True,
        verbose_name="Магазин (пусто — глобально)",
    )
    percent = models.DecimalField("Процент", max_digits=5, decimal_places=2)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Правило комиссии"
        verbose_name_plural = "Правила комиссии"

    def __str__(self):
        target = self.shop.name if self.shop else "глобально"
        return f"{self.percent}% — {target}"


class Commission(models.Model):
    """Запись комиссии по конкретному заказу для конкретного магазина."""

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="commissions", verbose_name="Заказ"
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="commissions", verbose_name="Магазин"
    )
    shop_subtotal = models.DecimalField("Сумма магазина", max_digits=12, decimal_places=2)
    rate = models.DecimalField("Ставка, %", max_digits=5, decimal_places=2)
    amount = models.DecimalField("Комиссия", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Комиссия"
        verbose_name_plural = "Комиссии"

    def __str__(self):
        return f"{self.order.number}: {self.shop.name} — {self.amount} сом"


class SellerWallet(models.Model):
    """Баланс продавца: заработанное за вычетом комиссий и выплат."""

    shop = models.OneToOneField(
        "shops.Shop", on_delete=models.CASCADE, related_name="wallet", verbose_name="Магазин"
    )
    available = models.DecimalField("Доступно к выводу", max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField("Заработано всего", max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Кошелёк продавца"
        verbose_name_plural = "Кошельки продавцов"

    def __str__(self):
        return f"{self.shop.name}: {self.available} сом"


class PayoutStatus(models.TextChoices):
    PENDING = "pending", "В обработке"
    PROCESSING = "processing", "Выполняется"
    SUCCEEDED = "succeeded", "Выплачено"
    FAILED = "failed", "Ошибка"


class Payout(models.Model):
    """Заявка продавца на вывод средств."""

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="payouts", verbose_name="Магазин"
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    status = models.CharField("Статус", max_length=20, choices=PayoutStatus.choices, default=PayoutStatus.PENDING)
    provider_payout_id = models.CharField("ID в платёжной системе", max_length=255, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    completed_at = models.DateTimeField("Завершена", null=True, blank=True)

    class Meta:
        verbose_name = "Выплата"
        verbose_name_plural = "Выплаты"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.shop.name}: {self.amount} сом ({self.status})"


class Transaction(models.Model):
    """Аудит-журнал движения средств по кошельку."""

    class Type(models.TextChoices):
        EARN = "earn", "Доход с заказа"
        COMMISSION = "commission", "Комиссия платформы"
        PAYOUT = "payout", "Выплата"
        REFUND = "refund", "Возврат"

    wallet = models.ForeignKey(
        SellerWallet, on_delete=models.CASCADE, related_name="transactions", verbose_name="Кошелёк"
    )
    type = models.CharField("Тип", max_length=20, choices=Type.choices)
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions", verbose_name="Заказ"
    )
    payout = models.ForeignKey(
        Payout, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions", verbose_name="Выплата"
    )
    comment = models.CharField("Комментарий", max_length=255, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Операция"
        verbose_name_plural = "Операции"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.wallet.shop.name}: {self.type} {self.amount} сом"
