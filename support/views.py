from django.db.models import Count
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from core.services import notify

from .models import SupportMessage, SupportTicket, TicketStatus
from .serializers import (
    SupportMessageSerializer,
    SupportTicketSerializer,
    SupportTicketStaffUpdateSerializer,
)


def _ticket_queryset():
    return SupportTicket.objects.select_related("user", "assignee").annotate(
        messages_count=Count("messages")
    )


class TicketListCreateAPIView(generics.ListCreateAPIView):
    """GET — мои тикеты (оператор видит все), POST — создать обращение."""

    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "priority"]

    def get_queryset(self):
        qs = _ticket_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        ticket = serializer.save(user=self.request.user)


class TicketDetailAPIView(generics.RetrieveAPIView):
    """Детали тикета + сообщения. Доступ: автор или оператор."""

    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _ticket_queryset()

    def get_object(self):
        ticket = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        if not ticket.has_access(self.request.user):
            self.permission_denied(self.request)
        return ticket


class TicketStaffUpdateAPIView(generics.UpdateAPIView):
    """PATCH статуса/приоритета/назначения — только оператор."""

    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketStaffUpdateSerializer
    permission_classes = [IsAdminUser]

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        ticket = serializer.save()
        # Взял в работу / решил — уведомляем автора о смене статуса на значимый
        if ticket.status != old_status and ticket.status in (TicketStatus.RESOLVED,):
            notify(
                ticket.user,
                type="support.reply",
                title=f"Обращение #{ticket.pk} решено",
                text=ticket.subject,
                link=f"/api/support/tickets/{ticket.pk}/",
            )


class TicketMessageCreateAPIView(generics.CreateAPIView):
    """POST сообщения в тикет. Ответ оператора → статус in_progress + уведомление автору."""

    serializer_class = SupportMessageSerializer
    permission_classes = [IsAuthenticated]

    def _get_ticket(self):
        ticket = get_object_or_404(_ticket_queryset(), pk=self.kwargs["pk"])
        if not ticket.has_access(self.request.user):
            self.permission_denied(self.request)
        return ticket

    def create(self, request, *args, **kwargs):
        ticket = self._get_ticket()
        if ticket.status == TicketStatus.CLOSED:
            return Response(
                {"detail": "Обращение закрыто — создайте новое"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(ticket=ticket, author=request.user)

        if request.user.is_staff:
            # Оператор ответил: тикет в работе + уведомление автору
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.IN_PROGRESS
                ticket.save(update_fields=["status", "updated_at"])
            notify(
                ticket.user,
                type="support.reply",
                title=f"Ответ поддержки по обращению #{ticket.pk}",
                text=message.text[:100],
                link=f"/api/support/tickets/{ticket.pk}/",
                email=True,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
