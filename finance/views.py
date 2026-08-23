from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from shops.permissions import IsSeller
from .models import Payout, PayoutStatus, Transaction
from .serializers import *
from .services import WalletService


class MyWalletAPIView(APIView):
    permission_classes = [IsSeller]

    def get(self, request):
        shop = request.user.shop
        wallet = WalletService.get_or_create_wallet(shop)
        return Response(
            {
                "wallet": WalletSerializer(wallet).data,
                "transactions": TransactionSerializer(wallet.transactions.all(), many=True).data,
            }
        )


class PayoutListCreateAPIView(APIView):
    permission_classes = [IsSeller]

    def get(self, request):
        payouts = Payout.objects.filter(shop=request.user.shop)
        return Response(PayoutSerializer(payouts, many=True).data)

    def post(self, request):
        amount = request.data.get("amount")
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return Response({"error": "Некорректная сумма"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payout = WalletService.request_payout(request.user.shop, amount)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class PayoutMarkAPIView(APIView):
    """Админ отмечает выплату исполненной или ошибочной."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        payout = get_object_or_404(Payout, pk=pk)
        status_name = request.data.get("status")
        if status_name not in PayoutStatus.values:
            return Response({"error": "Некорректный статус"}, status=status.HTTP_400_BAD_REQUEST)
        payout = WalletService.mark_payout(payout.pk, status_name, request.data.get("provider_payout_id", ""))
        return Response(PayoutSerializer(payout).data)
