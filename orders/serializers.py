from rest_framework import serializers

from .models import *
from catalog.serializers import ProductListSerializer


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["recipient_name", "phone", "address", "comment", "payment_method"]

    def validate_payment_method(self, value):
        if value not in PaymentMethod.values:
            raise serializers.ValidationError("Некорректный способ оплаты")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "price", "quantity", "subtotal"]


class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "number", "status", "get_status_display", "payment_method",
            "total", "items_count", "payment_status", "created_at",
        ]

    def get_items_count(self, obj):
        return obj.order_items.count()

    def get_payment_status(self, obj):
        return obj.payment.status if hasattr(obj, "payment") else None


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + [
            "recipient_name", "phone", "address", "comment", "items",
        ]


class SellerOrderSerializer(OrderListSerializer):
    class Meta(OrderListSerializer.Meta):
        pass


class SellerOrderDetailSerializer(OrderDetailSerializer):
    class Meta(OrderDetailSerializer.Meta):
        pass
