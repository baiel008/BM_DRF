from rest_framework import serializers

from .models import *


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "text", "link", "is_read", "created_at"]


class ShopFollowSerializer(serializers.ModelSerializer):
    shop = serializers.SerializerMethodField()

    class Meta:
        model = ShopFollow
        fields = ["id", "shop", "created_at"]

    def get_shop(self, obj):
        from shops.serializers import ShopListSerializer

        return ShopListSerializer(obj.shop, context=self.context).data
