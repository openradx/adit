from .base import *  # noqa: F403
from .base import env

DEBUG = True

ENVIRONMENT = "development"

INTERNAL_IPS = env.list("DJANGO_INTERNAL_IPS")

REMOTE_DEBUGGING_ENABLED = env.bool("REMOTE_DEBUGGING_ENABLED", default=False)
REMOTE_DEBUGGING_PORT = env.int("REMOTE_DEBUGGING_PORT", default=5678)

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

if env.bool("FORCE_DEBUG_TOOLBAR", default=True):
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda _: True}

LOGGING["loggers"]["adit"]["level"] = "DEBUG"  # noqa: F405

ENABLE_DICOM_DEBUG_LOGGER = False
