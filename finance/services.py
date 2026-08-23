from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Commission, CommissionRule, Payout, PayoutStatus, SellerWallet, Transaction


class WalletService:
    """Кошелёк продавца и расчёт комиссий."""

    @staticmethod
    def get_or_create_wallet(shop):
        wallet, _ = SellerWallet.objects.get_or_create(shop=shop)
        return wallet

    @staticmethod
    def _get_rule(shop):
        rule = CommissionRule.objects.filter(shop=shop, is_active=True).first()
        if not rule:
            rule = CommissionRule.objects.filter(shop__isnull=True, is_active=True).first()
        return rule

    @staticmethod
    @transaction.atomic
    def record_order(order):
        """Начисляет доход магазинам по заказу и удерживает комиссию платформы."""
        by_shop = {}
        for item in order.order_items.all():
            if not item.shop_id:
                continue
            by_shop.setdefault(item.shop_id, {"shop": item.shop, "subtotal": Decimal("0")})
            by_shop[item.shop_id]["subtotal"] += item.subtotal

        for data in by_shop.values():
            shop = data["shop"]
            subtotal = data["subtotal"]
            rule = WalletService._get_rule(shop)
            rate = rule.percent if rule else Decimal(str(settings.DEFAULT_COMMISSION_PERCENT))
            commission_amount = (subtotal * rate / Decimal("100")).quantize(Decimal("0.01"))

            wallet = WalletService.get_or_create_wallet(shop)
            wallet.available += subtotal - commission_amount
            wallet.total_earned += subtotal
            wallet.save()

            Commission.objects.create(
                order=order, shop=shop, shop_subtotal=subtotal, rate=rate, amount=commission_amount
            )
            Transaction.objects.create(
                wallet=wallet, type=Transaction.Type.EARN, amount=subtotal, order=order,
                comment=f"Доход по заказу {order.number}",
            )
            Transaction.objects.create(
                wallet=wallet, type=Transaction.Type.COMMISSION, amount=-commission_amount, order=order,
                comment=f"Комиссия платформы ({rate}%) по заказу {order.number}",
            )
        return order

    @staticmethod
    @transaction.atomic
    def reverse_order(order):
        """Полный возврат: списывает доход с кошельков магазинов и удаляет начисленную комиссию."""
        for commission in Commission.objects.filter(order=order).select_related("shop"):
            wallet = WalletService.get_or_create_wallet(commission.shop)
            wallet.available -= commission.shop_subtotal - commission.amount
            wallet.total_earned -= commission.shop_subtotal
            wallet.save()
            Transaction.objects.create(
                wallet=wallet, type=Transaction.Type.REFUND, amount=-commission.shop_subtotal, order=order,
                comment=f"Возврат по заказу {order.number}",
            )
            commission.delete()
        return order

    @staticmethod
    @transaction.atomic
    def reverse_order_partial(order, ratio):
        """Частичный возврат: пропорционально уменьшает доход магазинов и пересчитывает комиссию.
        ratio — доля возвращаемой суммы от исходной суммы заказа (0 < ratio < 1)."""
        ratio = Decimal(str(ratio))
        for commission in Commission.objects.filter(order=order).select_related("shop"):
            refunded_subtotal = (commission.shop_subtotal * ratio).quantize(Decimal("0.01"))
            new_subtotal = commission.shop_subtotal - refunded_subtotal
            new_amount = (new_subtotal * commission.rate / Decimal("100")).quantize(Decimal("0.01"))
            delta = (new_subtotal - new_amount) - (commission.shop_subtotal - commission.amount)

            wallet = WalletService.get_or_create_wallet(commission.shop)
            wallet.available += delta
            wallet.total_earned -= refunded_subtotal
            wallet.save()
            Transaction.objects.create(
                wallet=wallet, type=Transaction.Type.REFUND, amount=delta, order=order,
                comment=f"Частичный возврат по заказу {order.number}",
            )
            commission.shop_subtotal = new_subtotal
            commission.amount = new_amount
            commission.save(update_fields=["shop_subtotal", "amount"])
        return order

    @staticmethod
    @transaction.atomic
    def request_payout(shop, amount):
        wallet = WalletService.get_or_create_wallet(shop)
        if amount <= 0:
            raise ValueError("Сумма должна быть больше нуля")
        if amount > wallet.available:
            raise ValueError("Недостаточно средств на кошельке")

        payout = Payout.objects.create(shop=shop, amount=amount)
        wallet.available -= amount
        wallet.save()
        Transaction.objects.create(
            wallet=wallet, type=Transaction.Type.PAYOUT, amount=-amount, payout=payout,
            comment=f"Выплата №{payout.pk}",
        )
        return payout

    @staticmethod
    @transaction.atomic
    def mark_payout(payout_id, status, provider_id=""):
        payout = Payout.objects.select_related("shop").get(pk=payout_id)
        previous = payout.status
        if status == PayoutStatus.SUCCEEDED:
            payout.completed_at = timezone.now()
        if status == PayoutStatus.FAILED and previous != PayoutStatus.FAILED:
            wallet = WalletService.get_or_create_wallet(payout.shop)
            wallet.available += payout.amount
            wallet.save()
            Transaction.objects.create(
                wallet=wallet, type=Transaction.Type.PAYOUT, amount=payout.amount, payout=payout,
                comment=f"Возврат средств после неудачной выплаты №{payout.pk}",
            )
        payout.status = status
        payout.provider_payout_id = provider_id or payout.provider_payout_id
        payout.save(update_fields=["status", "provider_payout_id", "completed_at"])
        return payout
