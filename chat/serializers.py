from django.conf import settings
from rest_framework import serializers

from .models import Message, Thread


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    attachment = serializers.ImageField(required=False, allow_null=True, use_url=True)

    class Meta:
        model = Message
        fields = ["id", "thread", "sender", "sender_name", "text", "attachment", "is_read", "created_at"]
        read_only_fields = ["thread", "sender", "is_read"]

    def get_sender_name(self, obj):
        return obj.sender.get_full_name() or obj.sender.email

    def validate_attachment(self, file):
        if file and file.size > settings.MAX_UPLOAD_IMAGE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"Файл больше {settings.MAX_UPLOAD_IMAGE_MB} МБ"
            )
        return file


class ThreadListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    shop_id = serializers.IntegerField(read_only=True)
    shop_name = serializers.CharField(source="shop.name", read_only=True, default=None)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = [
            "id", "title",
            "order", "order_number", "order_status",
            "product_id", "product_name", "shop_id", "shop_name",
            "last_message", "unread_count", "created_at",
        ]

    def get_title(self, obj):
        return str(obj)

    def get_order_number(self, obj):
        return obj.order.number if obj.order_id else None

    def get_order_status(self, obj):
        return obj.order.status if obj.order_id else None

    def get_last_message(self, obj):
        message = obj.messages.select_related("sender").last()
        return MessageSerializer(message).data if message else None

    def get_unread_count(self, obj):
        user = self.context["request"].user
        return obj.messages.exclude(sender=user).filter(is_read=False).count()


class ThreadCreateSerializer(serializers.Serializer):
    """Создание диалога по товару или магазину (заказ создаётся отдельным эндпоинтом)."""

    product_id = serializers.IntegerField(required=False)
    shop_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if bool(attrs.get("product_id")) == bool(attrs.get("shop_id")):
            raise serializers.ValidationError("Укажите ровно одно: product_id или shop_id")
        return attrs
