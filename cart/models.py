from django.conf import settings
from django.db import models


class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items", verbose_name="Пользователь"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="cart_items", verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField("Количество", default=1)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Позиция корзины"
        verbose_name_plural = "Позиции корзины"
        unique_together = ("user", "product")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.email}: {self.product.name} × {self.quantity}"

    @property
    def unit_price(self):
        return self.product.get_unit_price(self.quantity)

    @property
    def line_total(self):
        return self.unit_price * self.quantity
