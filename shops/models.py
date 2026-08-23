from django.conf import settings
from django.db import models


class Shop(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shop",
        verbose_name="Владелец",
    )
    name = models.CharField("Название магазина", max_length=120)
    slug = models.SlugField("Слаг", max_length=140, unique=True, blank=True)
    logo = models.ImageField("Логотип", upload_to="shop_logos/", blank=True)
    description = models.TextField("Описание", blank=True)
    city = models.CharField("Город", max_length=120)
    address = models.CharField("Адрес", max_length=255, blank=True)
    phone = models.CharField("Контактный телефон", max_length=30, blank=True)
    email = models.EmailField("Email", blank=True)
    managers_contacts = models.TextField("Контакты менеджеров", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from catalog.models import unique_slug

            self.slug = unique_slug(Shop, self.name, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    @property
    def rating(self):
        from django.db.models import Avg

        agg = self.products.filter(reviews__is_published=True).aggregate(
            avg=Avg("reviews__rating")
        )
        return agg["avg"] or 0

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()
