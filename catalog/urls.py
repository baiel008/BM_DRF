from django.urls import path

from . import views

urlpatterns = [
    path("feed/", views.HomeFeedAPIView.as_view(), name="home_feed"),
    path("categories/", views.CategoryListAPIView.as_view(), name="category_list"),
    path("categories/<slug:slug>/", views.CategoryDetailAPIView.as_view(), name="category_detail"),
    path("brands/", views.BrandListAPIView.as_view(), name="brand_list"),
    path("brands/<slug:slug>/", views.BrandDetailAPIView.as_view(), name="brand_detail"),
    path("products/", views.ProductListAPIView.as_view(), name="product_list"),
    path("products/<slug:slug>/", views.ProductDetailAPIView.as_view(), name="product_detail"),
    path("products/<slug:slug>/reviews/", views.ReviewListAPIView.as_view(), name="review_list"),
    path("products/<slug:slug>/review/", views.ReviewCreateAPIView.as_view(), name="review_create"),
    path("search/suggest/", views.SearchSuggestAPIView.as_view(), name="search_suggest"),
    path("favorites/", views.FavoriteListAPIView.as_view(), name="favorite_list"),
    path("favorites/toggle/<int:pk>/", views.FavoriteToggleAPIView.as_view(), name="favorite_toggle"),
]
