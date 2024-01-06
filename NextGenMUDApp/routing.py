# NextGenMUDApp/routing.py

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('nextgenmud/ws/', consumers.MyConsumer.as_asgi()),
]
