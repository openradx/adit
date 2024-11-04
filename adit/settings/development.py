from .base import *  # noqa: F403
from .base import env

DEBUG = True

INTERNAL_IPS = env.list("DJANGO_INTERNAL_IPS")

REMOTE_DEBUGGING_ENABLED = env.bool("REMOTE_DEBUGGING_ENABLED")
REMOTE_DEBUGGING_PORT = env.int("REMOTE_DEBUGGING_PORT")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
    "debug_permissions",
    "django_browser_reload",
]

MIDDLEWARE += [  # noqa: F405
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

if env.bool("FORCE_DEBUG_TOOLBAR"):
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda _: True}

LOGGING["loggers"]["adit"]["level"] = "DEBUG"  # noqa: F405

if env.bool("USE_DOCKER"):
    import socket

    # For Debug Toolbar to show up on Docker Compose in development mode.
    # This only works when browsed from the host where the containers are run.
    # If viewed from somewhere else then DJANGO_INTERNAL_IPS must be set.
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]  # noqa: F405

ENABLE_DICOM_DEBUG_LOGGER = False
