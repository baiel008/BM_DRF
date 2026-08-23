from rest_framework import serializers

from .models import CartItem
from catalog.models import Product
from catalog.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), source="product", write_only=True
    )
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "unit_price", "line_total"]

    def get_unit_price(self, obj):
        return float(obj.unit_price)

    def get_line_total(self, obj):
        return float(obj.line_total)


class CartAddSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField()


class CartGroupItemSerializer(serializers.Serializer):
    product = ProductListSerializer()
    quantity = serializers.IntegerField()
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    def get_unit_price(self, obj):
        return float(obj["unit_price"])

    def get_line_total(self, obj):
        return float(obj["line_total"])


class CartGroupSerializer(serializers.Serializer):
    shop = serializers.SerializerMethodField()
    items = CartGroupItemSerializer(many=True)
    total = serializers.SerializerMethodField()

    def get_shop(self, obj):
        from shops.serializers import ShopListSerializer

        return ShopListSerializer(obj["shop"], context=self.context).data

    def get_total(self, obj):
        return float(obj["total"])
