from rest_framework import serializers

from .models import *
from catalog.models import ProductImage
from catalog.serializers import ProductListSerializer, ProductDetailSerializer


class ShopListSerializer(serializers.ModelSerializer):
    rating = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            "id", "name", "slug", "logo", "city", "rating",
            "product_count", "followers_count", "created_at",
        ]

    def get_rating(self, obj):
        return float(obj.rating)

    def get_product_count(self, obj):
        return obj.product_count

    def get_followers_count(self, obj):
        return obj.followers.count()


class ShopDetailSerializer(ShopListSerializer):
    products = serializers.SerializerMethodField()

    class Meta(ShopListSerializer.Meta):
        fields = ShopListSerializer.Meta.fields + [
            "description", "address", "phone", "email", "managers_contacts", "products"
        ]

    def get_products(self, obj):
        products = obj.products.filter(is_active=True).select_related("category", "brand", "shop")
        return ProductListSerializer(products, many=True, context=self.context).data


class ShopCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = [
            "id", "name", "description", "city", "address", "phone",
            "email", "managers_contacts", "logo",
        ]


class SellerProductListSerializer(ProductListSerializer):
    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["sku", "stock", "created_at"]


class ProductImageUploadSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "url", "image", "alt", "is_main"]
        extra_kwargs = {"image": {"write_only": False}}

    def get_url(self, obj):
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class SellerProductDetailSerializer(ProductDetailSerializer):
    class Meta(ProductDetailSerializer.Meta):
        fields = ProductDetailSerializer.Meta.fields
