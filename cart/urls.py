from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.CartDetailAPIView.as_view(), name="cart_detail"),
    path("cart/add/", views.CartAddAPIView.as_view(), name="cart_add"),
    path("cart/<int:pk>/", views.CartUpdateAPIView.as_view(), name="cart_update"),
    path("cart/<int:pk>/remove/", views.CartRemoveAPIView.as_view(), name="cart_remove"),
]
