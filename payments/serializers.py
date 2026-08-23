from rest_framework import serializers

from .models import Payment


class PaymentCreateSessionSerializer(serializers.Serializer):
    return_url = serializers.CharField(default="")
    payment_id = serializers.IntegerField(required=False)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id", "order", "amount", "currency", "status", "method",
            "redirect_url", "paid_at", "created_at",
        ]
        read_only_fields = ["id", "amount", "currency", "status", "redirect_url", "paid_at", "created_at"]
