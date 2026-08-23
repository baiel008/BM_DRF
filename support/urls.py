from django.urls import path

from . import views

urlpatterns = [
    path("support/tickets/", views.TicketListCreateAPIView.as_view(), name="support_tickets"),
    path("support/tickets/<int:pk>/", views.TicketDetailAPIView.as_view(), name="support_ticket_detail"),
    path("support/tickets/<int:pk>/messages/", views.TicketMessageCreateAPIView.as_view(), name="support_ticket_messages"),
    path("support/tickets/<int:pk>/update/", views.TicketStaffUpdateAPIView.as_view(), name="support_ticket_update"),
]
