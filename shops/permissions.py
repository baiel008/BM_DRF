from rest_framework import permissions


class IsSeller(permissions.BasePermission):
    """Доступ только для пользователей со статусом продавца."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_seller)


class IsShopOwner(permissions.BasePermission):
    """Продавец управляет только своим магазином и своими товарами."""

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        shop = getattr(obj, "shop", None)
        if shop is None:
            shop = obj
        return shop.owner_id == request.user.id


class IsShopOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return IsShopOwner().has_object_permission(request, view, obj)
