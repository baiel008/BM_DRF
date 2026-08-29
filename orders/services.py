from django.db import transaction

from cart.services import CartService
from core.services import notify
from orders.models import Order, OrderItem
from payments.models import Payment
from shops.models import Shop


class OrderService:
    """Оформление заказа: транзакция, списание остатков, уведомления продавцов."""

    def __init__(self, user):
        self.user = user

    @transaction.atomic
    def create_order(self, data):
        cart = CartService(self.user)
        rows = cart.rows()
        if not rows:
            raise ValueError("Корзина пуста")

        out_of_stock = [r["product"].name for r in rows if r["product"].is_out_of_stock]
        if out_of_stock:
            raise ValueError(f"Товары закончились: {', '.join(out_of_stock)}")

        order = Order.objects.create(
            user=self.user,
            recipient_name=data["recipient_name"],
            phone=data["phone"],
            address=data["address"],
            comment=data.get("comment", ""),
            payment_method=data["payment_method"],
            total=cart.total(),
        )

        for row in rows:
            product = row["product"]
            unit_price = product.get_unit_price(row["quantity"])
            OrderItem.objects.create(
                order=order,
                product=product,
                shop=product.shop,
                product_name=product.name,
                price=unit_price,
                quantity=row["quantity"],
                subtotal=unit_price * row["quantity"],
            )
            product.stock = max(0, product.stock - row["quantity"])
            product.save(update_fields=["stock"])

        Payment.objects.create(order=order, user=self.user, amount=order.total, method=order.payment_method)

        # Уведомляем продавцов
        for shop_id in {row["product"].shop_id for row in rows}:
            shop = Shop.objects.filter(pk=shop_id).first()
            if shop and shop.owner:
                notify(
                    shop.owner,
                    type="seller.order_new",
                    title="Новый заказ",
                    text=f"Поступил заказ {order.number} на {len(rows)} позиций на сумму {order.total} сом",
                    link=f"/api/seller/orders/{order.pk}/",
                )

        cart.clear()
        return order
