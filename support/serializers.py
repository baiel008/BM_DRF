from django.conf import settings
from rest_framework import serializers

from users.models import User

from .models import SupportMessage, SupportTicket


class SupportTicketSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="user.email", read_only=True)
    assignee_email = serializers.SerializerMethodField()
    messages_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "id", "subject", "description", "status", "priority",
            "author_email", "assignee_email", "messages_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["status", "priority", "assignee"]

    def get_assignee_email(self, obj):
        return obj.assignee.email if obj.assignee else None

    def validate_subject(self, value):
        value = (value or "").strip()
        if len(value) < 5:
            raise serializers.ValidationError("Тема слишком короткая")
        return value

    def validate_description(self, value):
        value = (value or "").strip()
        if len(value) < 10:
            raise serializers.ValidationError("Опишите проблему подробнее")
        return value


class SupportTicketStaffUpdateSerializer(serializers.ModelSerializer):
    """Для оператора: статус, приоритет, назначение."""

    class Meta:
        model = SupportTicket
        fields = ["status", "priority", "assignee"]

    def validate_assignee(self, value):
        if value is not None and not value.is_staff:
            raise serializers.ValidationError("Назначать можно только на оператора (is_staff)")
        return value


class SupportMessageSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)
    is_from_staff = serializers.SerializerMethodField()
    attachment = serializers.ImageField(required=False, allow_null=True, use_url=True)

    class Meta:
        model = SupportMessage
        fields = ["id", "ticket", "author_email", "is_from_staff", "text", "attachment", "created_at"]
        read_only_fields = ["ticket"]

    def get_is_from_staff(self, obj):
        return obj.author.is_staff

    def validate_text(self, value):
        value = (value or "").strip()
        if not value and not self.initial_data.get("attachment"):
            raise serializers.ValidationError("Пустое сообщение")
        return value or ""

    def validate_attachment(self, file):
        if file and file.size > settings.MAX_UPLOAD_IMAGE_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Файл больше {settings.MAX_UPLOAD_IMAGE_MB} МБ")
        return file
