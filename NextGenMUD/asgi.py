# NextGenMUD/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import NextGenMUDApp.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NextGenMUD.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            NextGenMUDApp.routing.websocket_urlpatterns
        )
    ),
})
