from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _register_sqlite_unicode_funcs(sender, connection, **kwargs):
    """SQLite UPPER()/LOWER() не знают кириллицу — подменяем на Unicode-аналоги.
    Нужно, чтобы UPPER()/LOWER() работали для русских текстов (см. core.lookups)."""
    if connection.vendor != "sqlite":
        return
    db = connection.connection
    if db is None:
        return
    db.create_function("upper", 1, lambda v: v.upper() if v is not None else None)
    db.create_function("lower", 1, lambda v: v.lower() if v is not None else None)


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from core import lookups  # noqa: F401

        connection_created.connect(_register_sqlite_unicode_funcs)
