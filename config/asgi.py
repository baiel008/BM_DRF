"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from chat.consumers import ChatConsumer
from core.consumers import NotificationConsumer

application = ProtocolTypeRouter(
    {
        "http": django_asgi,
        "websocket": AllowedHostsOriginValidator(
            URLRouter(
                [
                    path("ws/notifications/", NotificationConsumer.as_asgi()),
                    path("ws/chat/<int:thread_id>/", ChatConsumer.as_asgi()),
                ]
            )
        ),
    }
)
