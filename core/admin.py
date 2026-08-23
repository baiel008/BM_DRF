from django.contrib import admin

from .models import Notification, ShopFollow


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("title", "user__email")


@admin.register(ShopFollow)
class ShopFollowAdmin(admin.ModelAdmin):
    list_display = ("user", "shop", "created_at")
    search_fields = ("user__email", "shop__name")
