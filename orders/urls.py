from django.urls import path

from . import views

urlpatterns = [
    path("orders/", views.OrderListAPIView.as_view(), name="order_list"),
    path("orders/<int:pk>/", views.OrderDetailAPIView.as_view(), name="order_detail"),
    path("checkout/", views.CheckoutAPIView.as_view(), name="checkout"),
]
