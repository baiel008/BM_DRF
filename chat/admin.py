from django.contrib import admin

from .models import Message, Thread


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "created_at")
    search_fields = ("order__number",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "text", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("text", "sender__email")
