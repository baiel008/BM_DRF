"""Провайдеры платежей. Абстракция позволяет менять Stripe на ЮKassa/СБП одной реализацией."""

from abc import ABC, abstractmethod

import stripe
from django.conf import settings


class PaymentProvider(ABC):
    name = "base"

    @abstractmethod
    def create_payment(self, payment, return_url):
        """Создаёт платёж в ПС, возвращает {provider_id, redirect_url}."""

    @abstractmethod
    def verify_webhook(self, request):
        """Проверяет подпись вебхука и возвращает объект события."""

    @abstractmethod
    def refund(self, payment, amount=None):
        """Возврат: полный или частичный."""


class StripeProvider(PaymentProvider):
    name = "stripe"

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def create_payment(self, payment, return_url):
        session = stripe.checkout.Session.create(
            idempotency_key=f"payment-{payment.pk}",
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": settings.STRIPE_CURRENCY,
                        "unit_amount": int(payment.amount * 100),
                        "product_data": {"name": f"Заказ {payment.order.number}"},
                    },
                    "quantity": 1,
                }
            ],
            metadata={"order_id": payment.order_id, "payment_id": payment.pk},
            success_url=settings.PAYMENT_SUCCESS_URL,
            cancel_url=settings.PAYMENT_CANCEL_URL,
        )
        return {"provider_id": session.id, "redirect_url": session.url}

    def verify_webhook(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise PermissionError("Invalid signature")

    def refund(self, payment, amount=None):
        return stripe.Refund.create(
            payment_intent=payment.provider_payment_id,
            amount=int(amount * 100) if amount else None,
        )


class ManualProvider(PaymentProvider):
    """Заглушка для наличных при получении и для разработки без ключей Stripe."""

    name = "manual"

    def create_payment(self, payment, return_url):
        return {"provider_id": f"manual-{payment.pk}", "redirect_url": ""}

    def verify_webhook(self, request):
        raise NotImplementedError

    def refund(self, payment, amount=None):
        return {"status": "succeeded"}


def get_provider(payment):
    """Возвращает реализацию провайдера для платежа."""
    if payment.method in ("cash",) or not settings.STRIPE_SECRET_KEY:
        return ManualProvider()
    return StripeProvider()
