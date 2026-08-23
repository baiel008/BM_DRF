from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Пользователь",
    )
    title = models.CharField("Заголовок", max_length=120)
    text = models.TextField("Текст", blank=True)
    link = models.CharField("Ссылка", max_length=255, blank=True)
    is_read = models.BooleanField("Прочитано", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class ShopFollow(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_shops",
        verbose_name="Пользователь",
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="followers", verbose_name="Магазин"
    )
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "Подписка на магазин"
        verbose_name_plural = "Подписки на магазины"
        unique_together = ("user", "shop")

    def __str__(self):
        return f"{self.user.email} → {self.shop.name}"
