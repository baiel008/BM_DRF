from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import CartItem
from .serializers import *
from .services import CartService


class CartDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = CartService(request.user)
        groups = service.grouped_by_shop()
        serializer = CartGroupSerializer(
            [{"shop": g["shop"], "items": g["items"], "total": g["total"]} for g in groups],
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "groups": serializer.data,
                "total": float(service.total()),
                "count": service.count(),
            }
        )


class CartAddAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from catalog.models import Product

        product = Product.objects.filter(pk=serializer.validated_data["product_id"], is_active=True).first()
        if not product:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)
        if product.is_out_of_stock:
            return Response({"error": "Товар закончился"}, status=status.HTTP_400_BAD_REQUEST)
        service = CartService(request.user)
        item = service.add(product, serializer.validated_data["quantity"])
        return Response(
            {"ok": True, "item": CartItemSerializer(item, context={"request": request}).data, "count": service.count()},
            status=status.HTTP_201_CREATED,
        )


class CartUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = CartUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = CartItem.objects.filter(pk=pk, user=request.user).first()
        if not item:
            return Response({"error": "Позиция не найдена"}, status=status.HTTP_404_NOT_FOUND)
        quantity = serializer.validated_data["quantity"]
        service = CartService(request.user)
        if quantity <= 0:
            item.delete()
        else:
            item.quantity = min(quantity, item.product.stock) if item.product.stock > 0 else quantity
            item.save()
        return Response({"ok": True, "count": service.count(), "total": float(service.total())})


class CartRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        CartItem.objects.filter(pk=pk, user=request.user).delete()
        service = CartService(request.user)
        return Response({"ok": True, "count": service.count(), "total": float(service.total())})
