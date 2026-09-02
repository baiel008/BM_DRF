from rest_framework import serializers

from .models import *


class CategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "image"]


class CategoryDetailSerializer(serializers.ModelSerializer):
    children = CategoryListSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "image", "description", "children"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "image"]


class SellerBrandListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "image", "status", "status_display", "rejection_reason"]


class SellerBrandCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "image"]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Укажите название бренда")
        if Brand.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Бренд с таким названием уже существует")
        return value


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "url", "alt", "is_main"]

    def get_url(self, obj):
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class WholesaleTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = WholesaleTier
        fields = ["id", "min_qty", "price"]


class ProductListSerializer(serializers.ModelSerializer):
    main_image = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()
    has_wholesale = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "price", "old_price", "wholesale_price",
            "wholesale_min_qty", "stock", "volume", "color", "is_bestseller",
            "rating", "rating_count", "has_discount", "discount_percent",
            "is_new", "has_wholesale", "main_image",
        ]

    def get_main_image(self, obj):
        image = obj.main_image
        if not image:
            return None
        request = self.context.get("request")
        url = image.image.url
        return request.build_absolute_uri(url) if request else url

    def get_rating(self, obj):
        return float(obj.rating)

    def get_rating_count(self, obj):
        return obj.rating_count

    def get_has_discount(self, obj):
        return obj.has_discount

    def get_discount_percent(self, obj):
        return obj.discount_percent

    def get_is_new(self, obj):
        return obj.is_new

    def get_has_wholesale(self, obj):
        return obj.has_wholesale


class ProductDetailSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    wholesale_tiers = WholesaleTierSerializer(many=True, read_only=True)
    related_products = serializers.SerializerMethodField()
    shop = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()
    is_out_of_stock = serializers.SerializerMethodField()
    has_wholesale = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "name_ru", "name_ky", "name_en",
            "description", "description_ru", "description_ky", "description_en",
            "slug", "sku", "price", "old_price",
            "wholesale_price", "wholesale_min_qty", "stock", "volume", "color",
            "country", "category", "brand", "shop", "rating", "rating_count",
            "has_discount", "discount_percent", "is_new", "is_out_of_stock",
            "has_wholesale", "main_image", "images", "wholesale_tiers",
            "related_products", "views_count", "created_at",
        ]

    def get_main_image(self, obj):
        image = obj.main_image
        if not image:
            return None
        request = self.context.get("request")
        url = image.image.url
        return request.build_absolute_uri(url) if request else url

    def get_rating(self, obj):
        return float(obj.rating)

    def get_rating_count(self, obj):
        return obj.rating_count

    def get_has_discount(self, obj):
        return obj.has_discount

    def get_discount_percent(self, obj):
        return obj.discount_percent

    def get_is_new(self, obj):
        return obj.is_new

    def get_is_out_of_stock(self, obj):
        return obj.is_out_of_stock

    def get_has_wholesale(self, obj):
        return obj.has_wholesale

    def get_shop(self, obj):
        from shops.serializers import ShopListSerializer

        return ShopListSerializer(obj.shop, context=self.context).data

    def get_related_products(self, obj):
        related = (
            Product.objects.filter(category=obj.category, is_active=True)
            .exclude(pk=obj.pk)
            .select_related("category", "brand", "shop")
            .prefetch_related("images")
            .order_by("-is_bestseller", "-views_count")[:8]
        )
        return ProductListSerializer(related, many=True, context=self.context).data


class ProductCreateSerializer(serializers.ModelSerializer):
    name_ru = serializers.CharField(max_length=200, required=False, allow_blank=True)
    name_ky = serializers.CharField(max_length=200, required=False, allow_blank=True)
    name_en = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description_ru = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description_ky = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description_en = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Product
        fields = [
            "id", "category", "brand", "name", "description", "sku", "price",
            "old_price", "wholesale_price", "wholesale_min_qty", "stock",
            "volume", "color", "country", "is_active", "is_bestseller",
            "name_ru", "name_ky", "name_en",
            "description_ru", "description_ky", "description_en",
        ]
        extra_kwargs = {
            "sku": {"read_only": True},
        }

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше нуля")
        return value

    def validate_brand(self, brand):
        if not brand:
            return brand
        user = self.context["request"].user
        if brand.status == BrandStatus.APPROVED:
            return brand
        if brand.created_by_id == user.id and brand.status == BrandStatus.PENDING:
            return brand
        raise serializers.ValidationError("Этот бренд не прошёл модерацию и недоступен для товаров")

    def validate(self, attrs):
        wholesale_price = attrs.get("wholesale_price")
        wholesale_min_qty = attrs.get("wholesale_min_qty", 0)
        has_price = wholesale_price is not None
        has_qty = bool(wholesale_min_qty and wholesale_min_qty > 0)
        if has_price != has_qty:
            raise serializers.ValidationError(
                "Для оптовой продажи укажите и оптовую цену, и минимальное количество, либо оставьте оба поля пустыми"
            )
        return attrs

    def _apply_languages(self, attrs):
        name_ru = attrs.pop("name_ru", None)
        name_ky = attrs.pop("name_ky", None)
        name_en = attrs.pop("name_en", None)
        desc_ru = attrs.pop("description_ru", None)
        desc_ky = attrs.pop("description_ky", None)
        desc_en = attrs.pop("description_en", None)
        if name_ru is not None:
            attrs["name_ru"] = name_ru
        if name_ky is not None:
            attrs["name_ky"] = name_ky
        if name_en is not None:
            attrs["name_en"] = name_en
        if desc_ru is not None:
            attrs["description_ru"] = desc_ru
        if desc_ky is not None:
            attrs["description_ky"] = desc_ky
        if desc_en is not None:
            attrs["description_en"] = desc_en
        return attrs

    def create(self, validated_data):
        validated_data = self._apply_languages(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._apply_languages(validated_data)
        return super().update(instance, validated_data)


class ProductEditSerializer(ProductCreateSerializer):
    class Meta(ProductCreateSerializer.Meta):
        pass


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "product", "user", "rating", "text", "created_at"]

    def get_user(self, obj):
        from users.serializers import UserSimpleSerializer

        return UserSimpleSerializer(obj.user).data


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "rating", "text"]

    def validate(self, attrs):
        product = self.context.get("product")
        user = self.context["request"].user
        if not product or not product.can_review(user):
            raise serializers.ValidationError("Оставить отзыв можно только после завершённого заказа с этим товаром")
        if Review.objects.filter(product=product, user=user).exists():
            raise serializers.ValidationError("Вы уже оставили отзыв на этот товар")
        return attrs


class FavoriteSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), source="product", write_only=True
    )

    class Meta:
        model = Favorite
        fields = ["id", "product", "product_id", "created_at"]


class SearchSuggestSerializer(serializers.Serializer):
    label = serializers.CharField()
    sub = serializers.CharField()
    type = serializers.CharField()
    url = serializers.CharField()
