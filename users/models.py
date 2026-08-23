from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("Email", unique=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    avatar = models.ImageField("Фото профиля", upload_to="avatars/", blank=True)
    is_seller = models.BooleanField("Продавец", default=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.email


class Address(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="addresses", verbose_name="Пользователь"
    )
    label = models.CharField("Название", max_length=60, blank=True, default="")
    recipient_name = models.CharField("Получатель", max_length=120, blank=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    city = models.CharField("Город", max_length=120)
    address = models.CharField("Адрес", max_length=255)
    comment = models.CharField("Комментарий", max_length=255, blank=True)
    is_default = models.BooleanField("Основной", default=False)

    class Meta:
        verbose_name = "Адрес"
        verbose_name_plural = "Адреса"

    def __str__(self):
        return f"{self.recipient_name or self.user.email}, {self.city}, {self.address}"
