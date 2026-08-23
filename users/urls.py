from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeAPIView.as_view(), name="me"),
    path("me/password/", views.PasswordChangeAPIView.as_view(), name="me_password"),
    path("addresses/", views.AddressListCreateAPIView.as_view(), name="address_list"),
    path("addresses/<int:pk>/", views.AddressRetrieveUpdateDestroyAPIView.as_view(), name="address_detail"),
]
