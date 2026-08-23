from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from core.services import notify

from .models import Category, Brand, BrandStatus, Product, ProductImage, WholesaleTier, Review, Favorite


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class WholesaleTierInline(admin.TabularInline):
    model = WholesaleTier
    extra = 0


@admin.register(Category)
class CategoryAdmin(TranslationAdmin):
    list_display = ("name", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Brand)
class BrandAdmin(TranslationAdmin):
    list_display = ("name", "status", "created_by", "is_active")
    list_filter = ("status", "is_active")
    search_fields = ("name",)
    actions = ("approve_brands", "reject_brands")

    @admin.action(description="Одобрить выбранные бренды")
    def approve_brands(self, request, queryset):
        updated = 0
        for brand in queryset.exclude(status=BrandStatus.APPROVED):
            brand.status = BrandStatus.APPROVED
            brand.rejection_reason = ""
            brand.save(update_fields=["status", "rejection_reason"])
            if brand.created_by:
                notify(
                    brand.created_by,
                    type="brand.approved",
                    title="Бренд одобрен",
                    text=f"Ваш бренд «{brand.name}» прошёл модерацию.",
                    link="/api/seller/brands/",
                )
            updated += 1
        self.message_user(request, f"Одобрено брендов: {updated}")

    @admin.action(description="Отклонить выбранные бренды")
    def reject_brands(self, request, queryset):
        reason = "Не соответствует правилам маркетплейса"
        updated = 0
        for brand in queryset.exclude(status=BrandStatus.REJECTED):
            brand.status = BrandStatus.REJECTED
            brand.rejection_reason = reason
            brand.is_active = False
            brand.save(update_fields=["status", "rejection_reason", "is_active"])
            if brand.created_by:
                notify(
                    brand.created_by,
                    type="brand.rejected",
                    title="Бренд отклонён",
                    text=f"Бренд «{brand.name}» отклонён модератором.",
                    link="/api/seller/brands/",
                )
            updated += 1
        self.message_user(request, f"Отклонено брендов: {updated}")


@admin.register(Product)
class ProductAdmin(TranslationAdmin):
    list_display = ("name", "shop", "category", "brand", "price", "stock", "is_active", "is_bestseller")
    list_filter = ("is_active", "is_bestseller", "category", "brand")
    search_fields = ("name", "sku")
    inlines = [ProductImageInline, WholesaleTierInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_published", "created_at")
    list_filter = ("rating", "is_published")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
