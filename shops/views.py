from django.db.models import Sum
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import *
from .serializers import *
from .permissions import IsSeller, IsShopOwner, IsShopOwnerOrReadOnly
from catalog.models import Brand, BrandStatus, Product
from catalog.serializers import (
    ProductCreateSerializer,
    ProductEditSerializer,
    SellerBrandCreateSerializer,
    SellerBrandListSerializer,
)
from core.services import notify


def _get_own_shop(request):
    return Shop.objects.filter(owner=request.user).first()


# ─── Витрина ───────────────────────────────────────────────────────────────────

class ShopsDirectoryAPIView(generics.ListAPIView):
    queryset = Shop.objects.filter(is_active=True).select_related("owner")
    serializer_class = ShopListSerializer
    search_fields = ["name", "city", "description"]


class ShopDetailAPIView(generics.RetrieveAPIView):
    queryset = Shop.objects.filter(is_active=True).select_related("owner")
    serializer_class = ShopDetailSerializer
    lookup_field = "slug"


# ─── Стать продавцом ───────────────────────────────────────────────────────────

class BecomeSellerAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if Shop.objects.filter(owner=request.user).exists():
            return Response({"error": "Магазин уже создан"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ShopCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = serializer.save(owner=request.user)
        request.user.is_seller = True
        request.user.save(update_fields=["is_seller"])
        return Response(ShopDetailSerializer(shop, context={"request": request}).data, status=status.HTTP_201_CREATED)


# ─── Кабинет продавца ──────────────────────────────────────────────────────────

class SellerDashboardAPIView(APIView):
    permission_classes = [IsSeller]

    def get(self, request):
        shop = _get_own_shop(request)
        if not shop:
            return Response({"error": "Магазин не создан"}, status=status.HTTP_404_NOT_FOUND)
        products = Product.objects.filter(shop=shop)
        from orders.models import OrderItem

        items = OrderItem.objects.filter(shop=shop)
        from django.db.models import Count

        orders_count = items.values("order_id").distinct().count()
        sales_total = items.filter(order__status__in=["accepted", "processing", "preparing", "shipped", "completed"]).aggregate(
            total=Sum("subtotal")
        )["total"] or 0
        return Response(
            {
                "shop": ShopDetailSerializer(shop, context={"request": request}).data,
                "products_count": products.count(),
                "orders_count": orders_count,
                "sales_total": float(sales_total),
                "low_stock_count": products.filter(stock__lte=5).count(),
            }
        )


class SellerShopEditAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = ShopCreateUpdateSerializer
    permission_classes = [IsSeller, IsShopOwner]

    def get_object(self):
        shop = _get_own_shop(self.request)
        if not shop:
            self.permission_denied(self.request)
        self.check_object_permissions(self.request, shop)
        return shop


# ─── Бренды продавца ───────────────────────────────────────────────────────────

class SellerBrandListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsSeller]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SellerBrandCreateSerializer
        return SellerBrandListSerializer

    def get_queryset(self):
        return Brand.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        brand = serializer.save(
            created_by=self.request.user,
            status=BrandStatus.PENDING,
            is_active=False,
        )
        notify(
            self.request.user,
            type="brand.pending",
            title="Бренд отправлен на модерацию",
            text=f"Бренд «{brand.name}» создан и отправлен администратору на проверку.",
            link="/api/seller/brands/",
        )


# ─── Товары продавца ───────────────────────────────────────────────────────────

class SellerProductListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsSeller]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductCreateSerializer
        return SellerProductListSerializer

    def get_queryset(self):
        shop = _get_own_shop(self.request)
        if not shop:
            return Product.objects.none()
        return Product.objects.filter(shop=shop).select_related("category", "brand", "shop").prefetch_related("images")

    def perform_create(self, serializer):
        shop = _get_own_shop(self.request)
        serializer.save(shop=shop)


class SellerProductRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductEditSerializer
    permission_classes = [IsSeller, IsShopOwner]

    def get_queryset(self):
        shop = _get_own_shop(self.request)
        if not shop:
            return Product.objects.none()
        return Product.objects.filter(shop=shop)


# ─── Заказы продавца ───────────────────────────────────────────────────────────

class SellerOrderListAPIView(generics.ListAPIView):
    serializer_class = None
    permission_classes = [IsSeller]

    def get_serializer_class(self):
        from orders.serializers import SellerOrderSerializer

        return SellerOrderSerializer

    def get_queryset(self):
        from orders.models import OrderItem

        shop = _get_own_shop(self.request)
        order_ids = OrderItem.objects.filter(shop=shop).values_list("order_id", flat=True).distinct()
        from orders.models import Order

        return Order.objects.filter(pk__in=order_ids).prefetch_related("order_items")


class SellerOrderDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsSeller]

    def get_serializer_class(self):
        from orders.serializers import SellerOrderDetailSerializer

        return SellerOrderDetailSerializer

    def get_queryset(self):
        from orders.models import Order, OrderItem

        shop = _get_own_shop(self.request)
        order_ids = OrderItem.objects.filter(shop=shop).values_list("order_id", flat=True).distinct()
        return Order.objects.filter(pk__in=order_ids).prefetch_related("order_items")


class SellerOrderUpdateStatusAPIView(APIView):
    permission_classes = [IsSeller]

    def post(self, request, pk):
        from orders.models import Order, OrderItem, OrderStatus

        shop = _get_own_shop(request)
        if not OrderItem.objects.filter(order_id=pk, shop=shop).exists():
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)
        order = Order.objects.get(pk=pk)
        status_name = request.data.get("status")
        if status_name not in OrderStatus.values:
            return Response({"error": "Некорректный статус"}, status=status.HTTP_400_BAD_REQUEST)
        order.status = status_name
        order.save(update_fields=["status"])
        notify(
            order.user,
            type="order.status",
            title=f"Заказ {order.number}: {order.get_status_display()}",
            text=f"Продавец обновил статус вашего заказа на «{order.get_status_display()}».",
            link=f"/api/orders/{order.pk}/",
        )
        return Response({"status": order.status, "display": order.get_status_display()})


# ─── Продажи и склад ───────────────────────────────────────────────────────────

class SellerSalesAPIView(APIView):
    permission_classes = [IsSeller]

    def get(self, request):
        from orders.models import OrderItem

        shop = _get_own_shop(request)
        items = OrderItem.objects.filter(shop=shop)
        total = items.aggregate(total=Sum("subtotal"))["total"] or 0
        paid_total = items.filter(order__payment__status="succeeded").aggregate(total=Sum("subtotal"))["total"] or 0
        return Response(
            {
                "total_sales": float(total),
                "paid_sales": float(paid_total),
                "orders_count": items.values("order_id").distinct().count(),
                "units_sold": items.aggregate(s=Sum("quantity"))["s"] or 0,
            }
        )


class SellerStockAPIView(APIView):
    permission_classes = [IsSeller]

    def get(self, request):
        shop = _get_own_shop(request)
        products = Product.objects.filter(shop=shop).order_by("stock")
        return Response(SellerProductListSerializer(products, many=True, context={"request": request}).data)

    def patch(self, request):
        shop = _get_own_shop(request)
        product = get_object_or_404(Product, pk=request.data.get("product_id"), shop=shop)
        stock = request.data.get("stock")
        if stock is None or int(stock) < 0:
            return Response({"error": "Некорректный остаток"}, status=status.HTTP_400_BAD_REQUEST)
        product.stock = int(stock)
        product.save(update_fields=["stock"])
        return Response({"id": product.pk, "stock": product.stock})
