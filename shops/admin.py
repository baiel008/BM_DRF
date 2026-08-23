from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import Shop


@admin.register(Shop)
class ShopAdmin(TranslationAdmin):
    list_display = ("name", "owner", "city", "is_active")
    list_filter = ("is_active", "city")
    search_fields = ("name", "owner__email")
