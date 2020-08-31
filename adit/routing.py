from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from adit.selective_transfer import routing as selective_transfer_routing

application = ProtocolTypeRouter(
    {
        # (http->django views is added by default)
        "websocket": AuthMiddlewareStack(
            URLRouter(selective_transfer_routing.websocket_urlpatterns)
        ),
    }
)
