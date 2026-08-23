from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import *
from .serializers import *
from .filters import ProductFilter


# ─── Главная: подборки ─────────────────────────────────────────────────────────

@method_decorator(cache_page(60 * 5), name="dispatch")
@method_decorator(vary_on_headers("Accept-Language"), name="dispatch")
class HomeFeedAPIView(APIView):
    def get(self, request):
        base = Product.objects.filter(is_active=True, stock__gt=0).select_related(
            "category", "brand", "shop"
        ).prefetch_related("images")
        new = base.filter(created_at__gte=timezone.now() - timezone.timedelta(days=21))[:8]
        bestsellers = base.filter(is_bestseller=True)[:8]
        wholesale = base.filter(
            wholesale_price__isnull=False, wholesale_min_qty__gt=0
        ).order_by("-wholesale_min_qty")[:8]
        return Response(
            {
                "new": ProductListSerializer(new, many=True, context={"request": request}).data,
                "bestsellers": ProductListSerializer(bestsellers, many=True, context={"request": request}).data,
                "wholesale": ProductListSerializer(wholesale, many=True, context={"request": request}).data,
            }
        )


# ─── Категории ─────────────────────────────────────────────────────────────────

@method_decorator(cache_page(60 * 10), name="dispatch")
@method_decorator(vary_on_headers("Accept-Language"), name="dispatch")
class CategoryListAPIView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related("children")
    serializer_class = CategoryDetailSerializer


class CategoryDetailAPIView(generics.RetrieveAPIView):
    queryset = Category.objects.filter(is_active=True).prefetch_related("children")
    serializer_class = CategoryDetailSerializer
    lookup_field = "slug"


# ─── Бренды ────────────────────────────────────────────────────────────────────

class BrandListAPIView(generics.ListAPIView):
    queryset = Brand.objects.filter(is_active=True, status=BrandStatus.APPROVED)
    serializer_class = BrandSerializer
    search_fields = ["name"]


class BrandDetailAPIView(generics.RetrieveAPIView):
    queryset = Brand.objects.filter(is_active=True, status=BrandStatus.APPROVED)
    serializer_class = BrandSerializer
    lookup_field = "slug"


# ─── Товары ────────────────────────────────────────────────────────────────────

class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.filter(is_active=True).select_related(
        "category", "brand", "shop"
    ).prefetch_related("images", "wholesale_tiers")
    serializer_class = ProductListSerializer
    filterset_class = ProductFilter
    search_fields = ["name", "description", "sku", "brand__name", "shop__name"]
    ordering_fields = ["price", "-price", "created_at", "-views_count", "rating"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(name__u_icontains=q)
                | Q(description__u_icontains=q)
                | Q(sku__u_icontains=q)
                | Q(brand__name__u_icontains=q)
            )
        return qs


class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True).select_related(
        "category", "brand", "shop"
    ).prefetch_related("images", "wholesale_tiers", "reviews__user")
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.increase_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class SearchSuggestAPIView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "search"

    @swagger_auto_schema(manual_parameters=[openapi.Parameter("q", openapi.IN_QUERY, "Подстрока (минимум 2 символа)", type=openapi.TYPE_STRING)])
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response({"results": []})
        products = Product.objects.filter(is_active=True, name__u_icontains=q).select_related("shop")[:6]
        categories = Category.objects.filter(is_active=True, name__u_icontains=q)[:4]
        results = []
        for p in products:
            results.append(
                {
                    "label": p.name,
                    "sub": f"{p.price} ₽ · {p.shop.name}",
                    "type": "Товар",
                    "url": f"/api/products/{p.slug}/",
                }
            )
        for c in categories:
            results.append(
                {
                    "label": c.name,
                    "sub": "Категория",
                    "type": "Категория",
                    "url": f"/api/categories/{c.slug}/",
                }
            )
        return Response({"results": results[:10]})


# ─── Избранное ─────────────────────────────────────────────────────────────────

class FavoriteListAPIView(generics.ListAPIView):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related("product__shop", "product__brand")


class FavoriteToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        product = Product.objects.filter(pk=pk, is_active=True).first()
        if not product:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)
        fav, created = Favorite.objects.get_or_create(user=request.user, product=product)
        if not created:
            fav.delete()
        return Response({"added": created, "count": Favorite.objects.filter(user=request.user).count()})


# ─── Отзывы ────────────────────────────────────────────────────────────────────

class ReviewListAPIView(generics.ListAPIView):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return Review.objects.filter(product__slug=self.kwargs["slug"], is_published=True).select_related("user")


class ReviewCreateAPIView(generics.CreateAPIView):
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product"] = Product.objects.filter(slug=self.kwargs["slug"]).first()
        return context

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs["slug"])
        serializer.save(user=self.request.user, product=product)
