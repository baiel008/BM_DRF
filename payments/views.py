from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.services import notify
from orders.models import OrderItem

from .models import Payment
from .serializers import *
from .services import PaymentService


class PaymentCreateSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        payment = get_object_or_404(Payment, order_id=order_id, user=request.user)
        if payment.is_paid:
            return Response({"already_paid": True, "redirect_url": ""})
        result = PaymentService.create_session(payment.pk, request.data.get("return_url", ""))
        return Response(result)


class PaymentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        payment = get_object_or_404(Payment, order_id=order_id, user=request.user)
        return Response(PaymentSerializer(payment).data)


class PaymentRefundAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        payment = get_object_or_404(Payment, order_id=order_id, user=request.user)
        if not payment.is_paid:
            return Response({"error": "Заказ не оплачен"}, status=status.HTTP_400_BAD_REQUEST)
        amount = request.data.get("amount")
        try:
            amount = float(amount) if amount else None
        except (TypeError, ValueError):
            amount = None
        if amount and amount > float(payment.amount):
            return Response({"error": "Сумма возврата больше суммы платежа"}, status=status.HTTP_400_BAD_REQUEST)
        PaymentService.refund(payment, amount)
        return Response(PaymentSerializer(payment).data)


class PaymentWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        result = PaymentService.handle_webhook(request)
        code = result.pop("status", 200)
        return Response(result, status=code)


class PaymentConfirmAPIView(APIView):
    """Ручное подтверждение оплаты при получении (cash): продавец заказа или админ."""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        payment = get_object_or_404(Payment, order_id=order_id)
        is_admin = request.user.is_staff
        seller_has_items = OrderItem.objects.filter(order=payment.order, shop__owner=request.user).exists()
        if not (is_admin or seller_has_items):
            return Response({"error": "Нет прав на подтверждение"}, status=status.HTTP_403_FORBIDDEN)
        if payment.is_paid:
            return Response({"already_paid": True})
        if payment.method != "cash":
            return Response(
                {"error": "Подтверждение доступно только для оплаты при получении"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        PaymentService.confirm_payment(payment)
        notify(
            payment.user,
            type="order.paid",
            title="Оплата получена",
            text=f"Оплата по заказу {payment.order.number} подтверждена продавцом.",
            link=f"/api/orders/{payment.order.pk}/",
        )
        return Response(PaymentSerializer(payment).data)
