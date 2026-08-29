from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order, OrderItem


def public_stats():
    """Публичная витрина: только число зарегистрированных пользователей."""
    from users.models import User

    return {
        "total_users": User.objects.count(),
    }


def _days_ago(days):
    if days is None:
        return None
    return timezone.now() - timezone.timedelta(days=int(days))


def summary(days=30):
    """Полная коммерческая аналитика (по PIN)."""
    from users.models import User

    since = _days_ago(days)

    users_qs = User.objects.all()

    paid_orders = Order.objects.filter(payment__status="succeeded")
    if since:
        paid_orders = paid_orders.filter(created_at__gte=since)

    paid_items = OrderItem.objects.filter(order__in=paid_orders)

    gmv = paid_items.aggregate(total=Sum("subtotal"))["total"] or 0
    units = paid_items.aggregate(total=Sum("quantity"))["total"] or 0
    commission_pct = getattr(settings, "DEFAULT_COMMISSION_PERCENT", 0.0)
    commission = (gmv * Decimal(commission_pct) / Decimal(100)) if gmv else Decimal(0)

    new_users = users_qs.filter(created_at__gte=since) if since else users_qs.none()

    daily_users = (
        new_users
    ).annotate(date=TruncDate("created_at")).values("date").annotate(n=Count("id")).order_by("date")

    period_sales = paid_orders.filter(created_at__gte=since) if since else paid_orders.all()
    daily_sales = (
        period_sales
        .annotate(date=TruncDate("created_at")).values("date").annotate(
            orders=Count("id", distinct=True),
            gmv=Sum("order_items__subtotal"),
        ).order_by("date")
    )

    return {
        "users": {
            "total": users_qs.count(),
            "buyers": users_qs.filter(is_seller=False).count(),
            "sellers": users_qs.filter(is_seller=True).count(),
            "new_in_period": new_users.count(),
        },
        "sales": {
            "orders_paid": paid_orders.count(),
            "units_sold": units,
            "gmv": float(gmv),
            "platform_commission": float(commission),
        },
        "daily": _merge_daily(daily_users, daily_sales),
    }


def _merge_daily(user_rows, sales_rows):
    by_date = {}
    for row in user_rows:
        by_date.setdefault(str(row["date"]), {})["registrations"] = row["n"]
    for row in sales_rows:
        entry = by_date.setdefault(str(row["date"]), {})
        entry["orders"] = row["orders"]
        entry["gmv"] = float(row["gmv"] or 0)
    return [
        {"date": d, **v}
        for d, v in sorted(by_date.items())
    ]
