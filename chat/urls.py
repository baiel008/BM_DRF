from django.urls import path

from . import views

urlpatterns = [
    path("chat/threads/", views.ThreadListAPIView.as_view(), name="thread_list"),
    path("chat/threads/create/", views.ThreadCreateAPIView.as_view(), name="thread_create"),
    path("chat/threads/<int:pk>/messages/", views.ThreadMessagesAPIView.as_view(), name="thread_messages"),
    path("chat/threads/<int:pk>/messages/send/", views.ThreadMessageCreateAPIView.as_view(), name="thread_message_send"),
    path("chat/orders/<int:order_id>/thread/", views.ThreadCreateForOrderAPIView.as_view(), name="thread_for_order"),
]
