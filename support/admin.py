from django.contrib import admin

from .models import SupportMessage, SupportTicket


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ("author", "text", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "user", "status", "priority", "assignee", "updated_at")
    list_filter = ("status", "priority", "assignee", "created_at")
    search_fields = ("subject", "description", "user__email")
    list_editable = ("priority",)
    readonly_fields = ("user", "created_at", "updated_at")
    inlines = [SupportMessageInline]

    actions = ["take_in_progress", "mark_resolved", "mark_closed"]

    @admin.action(description="Взять в работу (назначить на себя)")
    def take_in_progress(self, request, queryset):
        queryset.update(status="in_progress", assignee=request.user)

    @admin.action(description="Пометить решённым")
    def mark_resolved(self, request, queryset):
        queryset.update(status="resolved")

    @admin.action(description="Закрыть обращения")
    def mark_closed(self, request, queryset):
        queryset.update(status="closed")


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "short_text", "created_at")
    search_fields = ("text", "author__email", "ticket__subject")

    @admin.display(description="Текст")
    def short_text(self, obj):
        return obj.text[:50]
