from .base import *  # noqa: F403
from .base import env

# Development settings

DEBUG = True

ENABLE_REMOTE_DEBUGGING = env("ENABLE_REMOTE_DEBUGGING")

SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# TODO: We also use Postgres for tests now. So tests can only run in the fullstack setup.
# if not ADIT_FULLSTACK and sys.argv and ("test" in sys.argv or "pytest" in sys.argv[0]):
#     DATABASES = {"default": env.db("SQLITE_URL", default="sqlite:///./adit-sqlite.db")}

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

if env("FORCE_DEBUG_TOOLBAR"):
    # https://github.com/jazzband/django-debug-toolbar/issues/1035
    from django.conf import settings

    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: settings.DEBUG}

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

ENABLE_DICOM_DEBUG_LOGGER = False

LOGGING["loggers"]["adit"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["celery"]["level"] = "DEBUG"  # noqa: F405

INTERNAL_IPS = env("DJANGO_INTERNAL_IPS")

if env("USE_DOCKER"):
    import socket

    # For Debug Toolbar to show up on Docker Compose in development mode.
    # This only works when browsed from the host where the containers are run.
    # If viewed from somewhere else then DJANGO_INTERNAL_IPS must be set.
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]
