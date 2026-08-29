from datetime import timedelta

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

SALT = "beauty-market-password-reset"
MAX_AGE = timedelta(hours=1)

signer = TimestampSigner(salt=SALT)


def make_token(user):
    """Подписанный одноразовый токен сброса пароля (TTL 1 час)."""
    return signer.sign(str(user.pk) + ":" + user.password[:32])


def check_token(email, token):
    """Возвращает user, если токен валиден для этого email, иначе None.

    Токен подписан значением пароля: после сброса старый токен
    автоматически перестаёт действовать (одноразовость).
    """
    from .models import User

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return None
    try:
        value = signer.unsign(token, max_age=MAX_AGE)
        pk, _, digest = value.partition(":")
        if pk == str(user.pk) and digest == user.password[:32]:
            return user
    except (BadSignature, SignatureExpired):
        pass
    return None
