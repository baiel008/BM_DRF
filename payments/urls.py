from django.urls import path

from . import views

urlpatterns = [
    path("payments/<int:order_id>/create/", views.PaymentCreateSessionAPIView.as_view(), name="payment_create"),
    path("payments/<int:order_id>/", views.PaymentDetailAPIView.as_view(), name="payment_detail"),
    path("payments/<int:order_id>/refund/", views.PaymentRefundAPIView.as_view(), name="payment_refund"),
    path("payments/<int:order_id>/confirm/", views.PaymentConfirmAPIView.as_view(), name="payment_confirm"),
    path("payments/webhook/stripe/", views.PaymentWebhookAPIView.as_view(), name="payment_webhook"),
]
