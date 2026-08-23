from django.conf import settings
from django.db import models


class Thread(models.Model):
    """Диалог покупатель ↔ продавец.

    Контекст (ровно один): заказ, товар или магазин.
    """

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="thread",
        null=True, blank=True, verbose_name="Заказ",
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, related_name="chat_threads",
        null=True, blank=True, verbose_name="Товар",
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="chat_threads",
        null=True, blank=True, verbose_name="Магазин",
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="initiated_chat_threads", null=True, blank=True,
        verbose_name="Инициатор (покупатель)",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"

    def __str__(self):
        if self.order_id:
            return f"Чат по заказу {self.order.number or self.order.pk}"
        if self.product_id:
            return f"Чат по товару «{self.product.name}»"
        if self.shop_id:
            return f"Чат по магазину {self.shop.name}"
        return f"Диалог #{self.pk}"

    def participants(self):
        """Все участники диалога (покупатель + продавцы)."""
        users = set()
        if self.initiator:
            users.add(self.initiator)
        elif self.order_id:
            users.add(self.order.user)
        if self.order_id:
            for item in self.order.order_items.select_related("shop__owner"):
                if item.shop and item.shop.owner:
                    users.add(item.shop.owner)
        elif self.product_id and self.product.shop.owner:
            users.add(self.product.shop.owner)
        elif self.shop_id and self.shop.owner:
            users.add(self.shop.owner)
        return users

    def has_access(self, user):
        return user.is_staff or user in self.participants()

    def others(self, sender):
        return [u for u in self.participants() if u != sender]


class Message(models.Model):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name="messages", verbose_name="Диалог"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages", verbose_name="Автор"
    )
    text = models.TextField("Текст")
    attachment = models.ImageField(
        "Вложение", upload_to="chat/%Y/%m/", blank=True,
    )
    is_read = models.BooleanField("Прочитано", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.sender}: {self.text[:30]}"
