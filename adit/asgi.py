"""
ASGI config for adit project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/

Adapted to use Channels, see
https://channels.readthedocs.io/en/latest/deploying.html#run-protocol-servers
"""

import os
import django
from channels.routing import get_default_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adit.settings.production")

django.setup()
application = get_default_application()
