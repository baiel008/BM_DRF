from django.contrib import admin

from .models import CommissionRule, Commission, SellerWallet, Payout, Transaction


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ("shop", "percent", "is_active")


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ("order", "shop", "shop_subtotal", "rate", "amount", "created_at")


@admin.register(SellerWallet)
class SellerWalletAdmin(admin.ModelAdmin):
    list_display = ("shop", "available", "total_earned")


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("shop", "amount", "status", "created_at", "completed_at")
    list_filter = ("status",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "type", "amount", "comment", "created_at")
    list_filter = ("type",)
