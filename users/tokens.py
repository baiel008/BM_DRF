import hashlib
import hmac
import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

# 4-значный код и политика ввода
CODE_LENGTH = 4
OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5


def generate_reset_code():
    """Случайный 4-значный код (0000–9999)."""
    return f"{random.SystemRandom().randrange(0, 10000):04d}"


def hash_code(code, user_pk):
    """Однонаправленный хеш кода: и в БД, и в письме нельзя восстановить код."""
    secret = settings.SECRET_KEY
    return hmac.new(
        secret.encode(),
        f"{user_pk}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def codes_match(raw_code, stored_hash, user_pk):
    """Безопасное сравнение кода с хешем (constant-time)."""
    return hmac.compare_digest(hash_code(raw_code, user_pk), stored_hash)


def mask_email(email):
    """Маскирует email для показа: user@gmail.com → u**r@gmail.com."""
    if "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "**"
    else:
        masked_local = local[0] + "**" + local[-1]
    return f"{masked_local}@{domain}"


def create_reset_code(user):
    """Создаёт и возвращает новый непросроченный 4-значный код сброса."""
    from .models import PasswordResetCode

    now = timezone.now()
    # старые активные коды пользователя аннулируем
    user.password_reset_codes.filter(used=False).update(used=True)

    code = generate_reset_code()
    PasswordResetCode.objects.create(
        user=user,
        code_hash=hash_code(code, user.pk),
        expires_at=now + OTP_TTL,
    )
    return code


def check_reset_code(email, code):
    """Возвращает (user, code_obj), если код валиден, иначе (None, None).

    Неудачные попытки увеличиваются здесь же (кроме случая, когда кода нет).
    """
    from .models import User

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return None, None

    code_obj = (
        user.password_reset_codes
        .filter(used=False, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .first()
    )
    if not code_obj:
        return None, None

    code_obj.attempts += 1
    if code_obj.attempts > OTP_MAX_ATTEMPTS:
        code_obj.used = True
    code_obj.save(update_fields=["attempts", "used"])

    if code_obj.used or not codes_match(code, code_obj.code_hash, user.pk):
        return None, None
    return user, code_obj


def invalidate_reset_code(code_obj):
    code_obj.used = True
    code_obj.save(update_fields=["used"])

    # срок жизни всех остальных активных кодов пользователя тоже завершаем
    code_obj.user.password_reset_codes.filter(used=False).update(used=True)