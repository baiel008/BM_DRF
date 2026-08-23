from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services import notify

from .models import Message, Thread
from .serializers import (
    MessageSerializer,
    ThreadCreateSerializer,
    ThreadListSerializer,
)


def _my_threads(user):
    return (
        Thread.objects.filter(
            Q(initiator=user)
            | Q(order__user=user)
            | Q(order__order_items__shop__owner=user)
            | Q(product__shop__owner=user)
            | Q(shop__owner=user)
        )
        .select_related("order", "product", "shop", "initiator")
        .distinct()
    )


class ThreadListAPIView(generics.ListAPIView):
    """Мои диалоги (покупатель или продавец)."""

    serializer_class = ThreadListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _my_threads(self.request.user)


class ThreadMessagesAPIView(generics.ListAPIView):
    """Сообщения диалога; заодно помечает чужие сообщения прочитанными."""

    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def _thread(self, request):
        thread = get_object_or_404(Thread, pk=self.kwargs["pk"])
        if not thread.has_access(request.user):
            self.permission_denied(request)
        return thread
    def get_queryset(self):
        return self._thread(self.request).messages.select_related("sender")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        self._thread(request).messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        return response


class ThreadMessageCreateAPIView(generics.CreateAPIView):
    """POST сообщения по REST (текст и/или картинка; WS — только текст)."""

    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        thread = get_object_or_404(Thread, pk=self.kwargs["pk"])
        if not thread.has_access(self.request.user):
            self.permission_denied(self.request)
        message = serializer.save(thread=thread, sender=self.request.user)
        for user in thread.others(self.request.user):
            name = self.request.user.get_full_name() or self.request.user.email
            notify(
                user,
                type="chat.message",
                title="Новое сообщение",
                text=f"{name}: {message.text[:80]}",
                link=f"/api/chat/threads/{thread.pk}/messages/",
            )


class ThreadCreateForOrderAPIView(APIView):
    """Получить/создать диалог по заказу."""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        from orders.models import Order

        order = get_object_or_404(Order, pk=order_id)
        if not (
            request.user.is_staff
            or order.user == request.user
            or order.order_items.filter(shop__owner=request.user).exists()
        ):
            return Response({"error": "Нет доступа к заказу"}, status=status.HTTP_403_FORBIDDEN)
        thread, created = Thread.objects.get_or_create(
            order=order, defaults={"initiator": order.user}
        )
        return Response(
            {**ThreadListSerializer(thread, context={"request": request}).data, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ThreadCreateAPIView(APIView):
    """Создать/получить диалог по товару или магазину."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ThreadCreateSerializer, responses={200: "Существующий диалог", 201: "Новый диалог"})
    def post(self, request):
        serializer = ThreadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        product = shop = None
        if data.get("product_id"):
            from catalog.models import Product

            product = get_object_or_404(Product, pk=data["product_id"], is_active=True)
            owner = product.shop.owner
            context = {"product": product}
        else:
            from shops.models import Shop

            shop = get_object_or_404(Shop, pk=data["shop_id"], is_active=True)
            owner = shop.owner
            context = {"shop": shop}

        if owner == request.user:
            return Response({"error": "Это ваш магазин"}, status=status.HTTP_400_BAD_REQUEST)

        thread, created = Thread.objects.get_or_create(initiator=request.user, **context)
        return Response(
            {**ThreadListSerializer(thread, context={"request": request}).data, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
