from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Payment, PaymentStatus
from .providers import get_provider


class PaymentService:
    """Оркестрация платежей: создание сессии, подтверждение, возвраты, вебхуки."""

    @staticmethod
    @transaction.atomic
    def create_session(payment_id, return_url):
        payment = Payment.objects.select_related("order").get(pk=payment_id)
        if payment.is_paid:
            return {"already_paid": True, "redirect_url": ""}
        if payment.redirect_url:
            return {"already_paid": False, "redirect_url": payment.redirect_url}

        provider = get_provider(payment)
        result = provider.create_payment(payment, return_url)
        payment.provider_payment_id = result["provider_id"]
        payment.redirect_url = result["redirect_url"]
        payment.status = PaymentStatus.PROCESSING
        payment.save(update_fields=["provider_payment_id", "redirect_url", "status"])
        return {"already_paid": False, "redirect_url": result["redirect_url"]}

    @staticmethod
    @transaction.atomic
    def confirm_payment(payment):
        if payment.is_paid:
            return payment
        payment.status = PaymentStatus.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at"])

        order = payment.order
        order.status = "paid"
        order.save(update_fields=["status"])

        from finance.services import WalletService

        WalletService.record_order(order)
        return payment

    @staticmethod
    def handle_webhook(request):
        """Входная точка вебхука: проверка подписи и диспатч по типу события."""
        from django.conf import settings as dj_settings

        if not dj_settings.STRIPE_WEBHOOK_SECRET:
            return {"error": "Stripe не настроен", "status": 503}

        from .providers import StripeProvider

        provider = StripeProvider()
        try:
            event = provider.verify_webhook(request)
        except PermissionError:
            return {"error": "Invalid signature", "status": 403}
        except ValueError:
            return {"error": "Invalid payload", "status": 400}

        event_type = event.get("type")

        # ── Оплата по Checkout Session ──
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            payment = Payment.objects.filter(pk=session.get("metadata", {}).get("payment_id")).first()
            if payment:
                payment.provider_payment_id = session.get("payment_intent")
                payment.save(update_fields=["provider_payment_id"])
                PaymentService.confirm_payment(payment)
            return {"status": 200}

        # ── Оплата по PaymentIntent ──
        if event_type == "payment_intent.succeeded":
            pi = event["data"]["object"]
            payment = Payment.objects.filter(provider_payment_id=pi.get("id")).first()
            if payment:
                PaymentService.confirm_payment(payment)
            return {"status": 200}

        # ── Возврат ──
        if event_type in ("charge.refunded", "refund.updated"):
            obj = event["data"]["object"]
            payment_intent_id = obj.get("payment_intent")
            if not payment_intent_id:
                charge = obj.get("charge")
                getter = getattr(charge, "get", None)
                if callable(getter):
                    payment_intent_id = getter("payment_intent")
            payment = None
            if payment_intent_id:
                payment = Payment.objects.filter(provider_payment_id=payment_intent_id).first()
            if payment:
                amount_refunded = obj.get("amount_refunded") or 0
                if amount_refunded and amount_refunded < int(payment.amount * 100):
                    payment.status = PaymentStatus.PARTIALLY_REFUNDED
                else:
                    payment.status = PaymentStatus.REFUNDED
                payment.save(update_fields=["status"])
            return {"status": 200}

        return {"status": 200, "ignored": event_type}

    @staticmethod
    @transaction.atomic
    def refund(payment, amount=None):
        """Инициирует возврат. amount=None — полный возврат.
        Полный возврат сторнирует начисления целиком, частичный — пропорционально сумме."""
        if payment.is_paid:
            from finance.services import WalletService

            if amount and amount < payment.amount:
                ratio = Decimal(str(amount)) / payment.amount
                WalletService.reverse_order_partial(payment.order, ratio)
            else:
                WalletService.reverse_order(payment.order)

        provider = get_provider(payment)
        provider.refund(payment, amount)
        if amount and amount < payment.amount:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED
        else:
            payment.status = PaymentStatus.REFUNDED
            payment.order.status = "cancelled"
            payment.order.save(update_fields=["status"])
        payment.save(update_fields=["status"])
        return payment
