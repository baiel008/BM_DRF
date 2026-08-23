from rest_framework import serializers

from .models import *


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerWallet
        fields = ["id", "available", "total_earned", "updated_at"]


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ["id", "amount", "status", "created_at", "completed_at"]
        read_only_fields = ["id", "status", "created_at", "completed_at"]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "type", "amount", "comment", "created_at"]


class CommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commission
        fields = ["id", "order", "shop", "shop_subtotal", "rate", "amount", "created_at"]
