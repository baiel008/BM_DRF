from django_filters import BooleanFilter, FilterSet

from .models import Product


class ProductFilter(FilterSet):
    wholesale = BooleanFilter(method="filter_wholesale", label="Только опт")

    class Meta:
        model = Product
        fields = {
            "category": ["exact"],
            "category__parent": ["exact"],
            "brand": ["exact"],
            "price": ["gt", "lt"],
            "is_bestseller": ["exact"],
            "is_active": ["exact"],
            "country": ["exact"],
        }

    def filter_wholesale(self, queryset, name, value):
        if value:
            return queryset.filter(wholesale_price__isnull=False, wholesale_min_qty__gt=0)
        return queryset
