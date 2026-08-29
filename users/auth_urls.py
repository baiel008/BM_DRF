from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from . import views

urlpatterns = [
    path("register/buyer/", views.RegisterBuyerAPIView.as_view(), name="register_buyer"),
    path("register/seller/", views.RegisterSellerAPIView.as_view(), name="register_seller"),
    path("login/", views.LoginAPIView.as_view(), name="login"),
    path("logout/", views.LogoutAPIView.as_view(), name="logout"),
    path("password/reset/", views.PasswordResetAPIView.as_view(), name="password_reset"),
    path("password/reset/confirm/", views.PasswordResetConfirmAPIView.as_view(), name="password_reset_confirm"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("verify/", TokenVerifyView.as_view(), name="token_verify"),
]
