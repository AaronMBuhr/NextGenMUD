# NextGenMUDApp/routing.py

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('nextgenmud/ws/', consumers.MyWebsocketConsumer.as_asgi()),
]
