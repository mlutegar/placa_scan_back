from django.urls import re_path
from . import consumers

print("Routing: Carregando backend/routing.py")

websocket_urlpatterns = [
    re_path(r'ws/video-stream/$', consumers.VideoStreamConsumer.as_asgi()),
]

print(f"Routing: websocket_urlpatterns definido como: {websocket_urlpatterns}")