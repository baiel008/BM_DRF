from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import *
from .serializers import *


# ─── Уведомления ───────────────────────────────────────────────────────────────

class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationMarkAllReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationUnreadCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"count": count})


class NotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"id": notification.pk, "is_read": True, "unread_count": unread})


# ─── Подписки на магазины ──────────────────────────────────────────────────────

class FollowedShopsListAPIView(generics.ListAPIView):
    serializer_class = ShopFollowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ShopFollow.objects.filter(user=self.request.user).select_related("shop")


class FollowShopToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from shops.models import Shop

        shop = Shop.objects.filter(pk=pk, is_active=True).first()
        if not shop:
            return Response({"error": "Магазин не найден"}, status=status.HTTP_404_NOT_FOUND)
        follow, created = ShopFollow.objects.get_or_create(user=request.user, shop=shop)
        if not created:
            follow.delete()
        return Response({"following": created, "followers_count": shop.followers.count()})
