import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from channels.security.websocket import AllowedHostsOriginValidator
import backend.routing # Importe diretamente para depurar

print("ASGI: Carregando asgi.py")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projeto_veicular_back.settings')

# Adicione este print para ver as URLs que estão sendo carregadas
print(f"ASGI: Rotas WebSocket carregadas: {backend.routing.websocket_urlpatterns}")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(backend.routing.websocket_urlpatterns))
        ),
    }
)
print("ASGI: ProtocolTypeRouter configurado.")