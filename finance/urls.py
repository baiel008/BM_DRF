from django.urls import path

from . import views

urlpatterns = [
    path("finance/wallet/", views.MyWalletAPIView.as_view(), name="wallet"),
    path("finance/payouts/", views.PayoutListCreateAPIView.as_view(), name="payouts"),
    path("finance/payouts/<int:pk>/mark/", views.PayoutMarkAPIView.as_view(), name="payout_mark"),
]
