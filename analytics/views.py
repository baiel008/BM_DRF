import secrets

from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .models import AnalyticsSession
from .services import public_stats, summary


class AnalyticsUnlockAPIView(APIView):
    """Ввод PIN → короткоживущая сессия доступа к аналитике."""

    permission_classes = [AllowAny]

    def post(self, request):
        pin = (request.data.get("pin") or "").strip()
        expected = settings.ANALYTICS_PASSWORD
        if not expected or pin != expected:
            return Response({"detail": "Неверный PIN"}, status=status.HTTP_401_UNAUTHORIZED)
        # сжигаем старые сессии (только одна активная)
        AnalyticsSession.objects.all().delete()
        session = AnalyticsSession.objects.create(token=secrets.token_urlsafe(32))
        return Response({"token": session.token})


class AnalyticsSummaryAPIView(APIView):
    """Коммерческая аналитика. Требует действующую PIN-сессию.

    Любой запрос продлевает last_seen (сбрасывает 15-сек таймер бездействия).
    """

    permission_classes = [AllowAny]

    def _session(self, request):
        token = request.headers.get("X-Analytics-Token") or request.query_params.get("token")
        if not token:
            return None
        session = AnalyticsSession.objects.filter(token=token).first()
        if not session or not session.is_active:
            return None
        # продлеваем окно (символично: auto_now сработает при save)
        session.save(update_fields=["last_seen"])
        return session

    def get(self, request):
        if not self._session(request):
            return Response(
                {"detail": "Доступ заблокирован. Введите PIN."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        days = request.query_params.get("days")
        return Response(summary(days=days if days is not None else 30))


class PublicStatsAPIView(APIView):
    """Публично: только число зарегистрированных пользователей."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(public_stats())
