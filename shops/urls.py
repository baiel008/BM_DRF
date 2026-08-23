from django.urls import path

from . import views

urlpatterns = [
    path("shops/", views.ShopsDirectoryAPIView.as_view(), name="shop_list"),
    path("shops/<slug:slug>/", views.ShopDetailAPIView.as_view(), name="shop_detail"),
    path("seller/become/", views.BecomeSellerAPIView.as_view(), name="become_seller"),
    path("seller/dashboard/", views.SellerDashboardAPIView.as_view(), name="seller_dashboard"),
    path("seller/shop/", views.SellerShopEditAPIView.as_view(), name="seller_shop_edit"),
    path("seller/brands/", views.SellerBrandListCreateAPIView.as_view(), name="seller_brand_list"),
    path("seller/products/", views.SellerProductListCreateAPIView.as_view(), name="seller_product_list"),
    path("seller/products/<int:pk>/", views.SellerProductRetrieveUpdateDestroyAPIView.as_view(), name="seller_product_detail"),
    path("seller/orders/", views.SellerOrderListAPIView.as_view(), name="seller_order_list"),
    path("seller/orders/<int:pk>/", views.SellerOrderDetailAPIView.as_view(), name="seller_order_detail"),
    path("seller/orders/<int:pk>/status/", views.SellerOrderUpdateStatusAPIView.as_view(), name="seller_order_status"),
    path("seller/sales/", views.SellerSalesAPIView.as_view(), name="seller_sales"),
    path("seller/stock/", views.SellerStockAPIView.as_view(), name="seller_stock"),
]
