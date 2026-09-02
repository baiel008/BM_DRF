from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Avg

import uuid

from unidecode import unidecode


def unique_slug(model, value, exclude_pk=None, max_length=120):
    base = slugify(unidecode(value)) or "item"
    slug = base[:max_length]
    qs = model.objects.filter(slug__iexact=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return slug
    for i in range(1, 1000):
        candidate = f"{base[: max_length - len(str(i)) - 1]}-{i}"
        if not model.objects.filter(slug__iexact=candidate).exists():
            return candidate
    return slug


class Category(models.Model):
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children", null=True, blank=True, verbose_name="Родитель"
    )
    name = models.CharField("Название", max_length=120)
    slug = models.SlugField("Слаг", max_length=140, unique=True, blank=True)
    image = models.ImageField("Изображение", upload_to="categories/", blank=True)
    icon = models.CharField("Иконка (emoji)", max_length=20, blank=True, default="")
    description = models.CharField("Описание", max_length=255, blank=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:category", kwargs={"slug": self.slug})


class BrandStatus(models.TextChoices):
    PENDING = "pending", "На модерации"
    APPROVED = "approved", "Одобрен"
    REJECTED = "rejected", "Отклонён"


class Brand(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)
    slug = models.SlugField("Слаг", max_length=140, unique=True, blank=True)
    image = models.ImageField("Логотип", upload_to="brands/", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="brands",
        null=True,
        blank=True,
        verbose_name="Кто создал",
    )
    status = models.CharField(
        "Статус модерации",
        max_length=20,
        choices=BrandStatus.choices,
        default=BrandStatus.APPROVED,
    )
    rejection_reason = models.TextField("Причина отказа", blank=True)

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Brand, self.name, exclude_pk=self.pk)
        super().save(*args, **kwargs)


class Product(models.Model):
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="products", verbose_name="Магазин"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категория"
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, related_name="products", null=True, blank=True, verbose_name="Бренд"
    )
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=220, unique=True, blank=True)
    description = models.TextField("Описание", blank=True)
    sku = models.CharField("Артикул", max_length=60, blank=True)
    price = models.DecimalField("Розничная цена", max_digits=10, decimal_places=2)
    old_price = models.DecimalField(
        "Старая цена", max_digits=10, decimal_places=2, null=True, blank=True
    )
    wholesale_price = models.DecimalField(
        "Оптовая цена", max_digits=10, decimal_places=2, null=True, blank=True
    )
    wholesale_min_qty = models.PositiveIntegerField("Мин. кол-во для опта", default=0)
    stock = models.PositiveIntegerField("Остаток на складе", default=0)
    volume = models.CharField("Объём/размер", max_length=60, blank=True)
    color = models.CharField("Цвет", max_length=60, blank=True)
    country = models.CharField("Страна производства", max_length=60, blank=True)
    is_active = models.BooleanField("Опубликован", default=True)
    is_bestseller = models.BooleanField("Хит продаж", default=False)
    views_count = models.PositiveIntegerField("Просмотры", default=0)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ("-created_at",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Product, self.name, exclude_pk=self.pk, max_length=220)
        if not self.sku:
            self.sku = self._generate_sku()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_sku():
        """Уникальный автоматический артикул вида BM-XXXXXXXX (8 hex)."""
        import secrets

        return f"BM-{secrets.token_hex(4).upper()}"

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def main_image(self):
        img = self.images.filter(is_main=True).first() or self.images.first()
        return img

    @property
    def has_discount(self):
        return self.old_price and self.old_price > self.price

    @property
    def is_new(self):
        return self.created_at >= timezone.now() - timezone.timedelta(days=21)

    @property
    def is_out_of_stock(self):
        return self.stock <= 0

    @property
    def has_wholesale(self):
        return self.wholesale_price is not None and self.wholesale_min_qty > 0

    @property
    def rating(self):
        agg = self.reviews.filter(is_published=True).aggregate(avg=Avg("rating"))
        return agg["avg"] or 0

    @property
    def rating_count(self):
        return self.reviews.filter(is_published=True).count()

    @property
    def discount_percent(self):
        if self.has_discount:
            return int((1 - self.price / self.old_price) * 100)
        return 0

    def get_wholesale_tiers(self):
        return self.wholesale_tiers.order_by("min_qty")

    def get_unit_price(self, qty):
        """Цена за единицу с учётом оптовых уровней."""
        tiers = list(self.get_wholesale_tiers())
        for tier in reversed(tiers):
            if qty >= tier.min_qty:
                return tier.price
        if self.has_wholesale and qty >= self.wholesale_min_qty:
            return self.wholesale_price
        return self.price

    def can_review(self, user):
        if not user.is_authenticated:
            return False
        from orders.models import OrderItem

        return OrderItem.objects.filter(
            order__user=user, product=self, order__status="completed"
        ).exists()

    def increase_views(self):
        Product.objects.filter(pk=self.pk).update(views_count=models.F("views_count") + 1)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images", verbose_name="Товар"
    )
    image = models.ImageField("Изображение", upload_to="products/")
    alt = models.CharField("Alt-текст", max_length=200, blank=True)
    is_main = models.BooleanField("Главное", default=False)

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"

    def __str__(self):
        return f"{self.product.name} — image"


class WholesaleTier(models.Model):
    """Дополнительный уровень оптовой цены: от N штук по цене X."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="wholesale_tiers", verbose_name="Товар"
    )
    min_qty = models.PositiveIntegerField("Кол-во, от")
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Оптовый уровень"
        verbose_name_plural = "Оптовые уровни"
        ordering = ("min_qty",)

    def __str__(self):
        return f"{self.product.name}: от {self.min_qty} шт. — {self.price} сом"


class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews", verbose_name="Товар"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews", verbose_name="Пользователь"
    )
    rating = models.PositiveSmallIntegerField("Оценка", choices=[(i, i) for i in range(1, 6)])
    text = models.TextField("Отзыв", blank=True)
    is_published = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        unique_together = ("product", "user")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.email}: {self.rating}★"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites", verbose_name="Пользователь"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="favorited_by", verbose_name="Товар"
    )
    created_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        unique_together = ("user", "product")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.email} → {self.product.name}"
