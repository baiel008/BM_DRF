from django.conf import settings
from django.db import models
from django.urls import reverse


class OrderStatus(models.TextChoices):
    NEW = "new", "Новый"
    ACCEPTED = "accepted", "Принят"
    PROCESSING = "processing", "В обработке"
    PREPARING = "preparing", "Готовится"
    SHIPPED = "shipped", "Передан"
    COMPLETED = "completed", "Завершён"
    CANCELLED = "cancelled", "Отменён"
    PAID = "paid", "Оплачен"


class PaymentMethod(models.TextChoices):
    CARD = "card", "Картой онлайн"
    CASH = "cash", "При получении"
    SBP = "sbp", "СБП"


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders", verbose_name="Покупатель"
    )
    number = models.CharField("Номер заказа", max_length=30, unique=True, blank=True)
    status = models.CharField("Статус", max_length=20, choices=OrderStatus.choices, default=OrderStatus.NEW, db_index=True)
    payment_method = models.CharField("Оплата", max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH)

    recipient_name = models.CharField("Получатель", max_length=120)
    phone = models.CharField("Телефон", max_length=30)
    address = models.CharField("Адрес доставки", max_length=255)
    comment = models.TextField("Комментарий", blank=True)
    seller_comment = models.TextField("Комментарий продавца", blank=True)

    total = models.DecimalField("Итого", max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-created_at",)

    def __str__(self):
        return self.number or f"Заказ #{self.pk}"

    def get_absolute_url(self):
        return reverse("orders:order_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        is_new = not self.number
        super().save(*args, **kwargs)
        if is_new:
            self.number = f"BM-{self.created_at:%y%m%d}-{self.pk:05d}"
            self.save(update_fields=["number"])

    @property
    def items(self):
        return self.order_items.select_related("product", "product__brand", "shop", "shop__owner")

    @property
    def is_paid(self):
        return hasattr(self, "payment") and self.payment.status == "succeeded"

    def items_for_shop(self, shop):
        return self.order_items.filter(shop=shop).select_related("product")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_items", verbose_name="Заказ")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, related_name="order_items", verbose_name="Товар"
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.SET_NULL, null=True, related_name="order_items", verbose_name="Магазин"
    )
    product_name = models.CharField("Название (снимок)", max_length=200)
    price = models.DecimalField("Цена за единицу", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("Количество")
    subtotal = models.DecimalField("Сумма", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
