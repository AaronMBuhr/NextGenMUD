# routing.py in the NextGenMUDApp app directory

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('nextgenmud/ws/', consumers.MyConsumer.as_asgi()),
    # Add other websocket routes here
]
