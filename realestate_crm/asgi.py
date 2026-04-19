"""
ASGI config for realestate_crm project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realestate_crm.settings")

application = get_asgi_application()

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path
from core.consumers import ChatConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate_crm.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path("ws/chat/<str:phone>/", ChatConsumer.as_asgi()),
    ]),
})
