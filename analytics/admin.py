from django.contrib import admin

from .models import AnalyticsSession


@admin.register(AnalyticsSession)
class AnalyticsSessionAdmin(admin.ModelAdmin):
    list_display = ("token", "created_at", "last_seen", "active")
    readonly_fields = ("token", "created_at", "last_seen")

    @admin.display(boolean=True, description="Активна")
    def active(self, obj):
        return obj.is_active
