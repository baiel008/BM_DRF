"""Настройки для тестов: фиктивный кэш, чтобы лимиты запросов
не накапливались между тестами в рамках одного процесса."""

from .settings import *  # noqa: F401,F403

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Celery: задачи выполняются синхронно в тестах
CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
