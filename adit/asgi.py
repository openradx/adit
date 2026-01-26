"""
ASGI config for adit project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/

Adapted to use Channels, see
https://channels.readthedocs.io/en/latest/deploying.html#run-protocol-servers
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adit.settings.development")

# Initialize OpenTelemetry before Django loads to ensure all requests are traced
from adit.telemetry import setup_opentelemetry  # noqa: E402

setup_opentelemetry()

from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from channels.sessions import SessionMiddlewareStack  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from adit.selective_transfer import routing as selective_transfer_routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            SessionMiddlewareStack(
                AuthMiddlewareStack(
                    URLRouter(selective_transfer_routing.websocket_urlpatterns),
                ),
            )
        ),
    }
)
