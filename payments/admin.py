from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "user", "amount", "status", "method", "provider", "paid_at", "created_at")
    list_filter = ("status", "method", "provider")
    search_fields = ("order__number", "user__email", "provider_payment_id")
