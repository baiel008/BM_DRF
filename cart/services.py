from django.db.models import Sum

from .models import CartItem


class CartService:
    """Логика корзины: группировка по магазинам, оптовые цены, итоги."""

    def __init__(self, user):
        self.user = user

    def items(self):
        return (
            CartItem.objects.filter(user=self.user, product__is_active=True)
            .select_related("product__shop", "product__shop__owner", "product__brand")
            .prefetch_related("product__wholesale_tiers")
        )

    def add(self, product, quantity=1):
        quantity = max(1, int(quantity))
        item, created = CartItem.objects.get_or_create(user=self.user, product=product)
        if not created:
            item.quantity = min(item.quantity + quantity, product.stock) if product.stock > 0 else item.quantity
        else:
            item.quantity = min(quantity, product.stock) if product.stock > 0 else quantity
        item.save()
        return item

    def update(self, product_id, quantity):
        item = self.items().filter(product_id=product_id).first()
        if not item:
            return None
        if quantity <= 0:
            item.delete()
            return None
        item.quantity = min(int(quantity), item.product.stock) if item.product.stock > 0 else int(quantity)
        item.save()
        return item

    def remove(self, product_id):
        self.items().filter(product_id=product_id).delete()

    def clear(self):
        self.items().delete()

    def rows(self):
        """Строки с ценами с учётом опта."""
        rows = []
        for item in self.items():
            rows.append(
                {
                    "product": item.product,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                }
            )
        return rows

    def grouped_by_shop(self):
        groups = {}
        for row in self.rows():
            shop = row["product"].shop
            groups.setdefault(shop.id, {"shop": shop, "items": [], "total": 0})
            groups[shop.id]["items"].append(row)
            groups[shop.id]["total"] += row["line_total"]
        return list(groups.values())

    def total(self):
        return sum(row["line_total"] for row in self.rows())

    def count(self):
        return self.items().aggregate(total=Sum("quantity"))["total"] or 0
