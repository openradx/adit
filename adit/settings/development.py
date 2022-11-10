from .base import *  # noqa: F403
from .base import env

# Development settings

DEBUG = True

ENABLE_REMOTE_DEBUGGING = env.bool("ENABLE_REMOTE_DEBUGGING", default=False)

SECRET_KEY = env.str(
    "DJANGO_SECRET_KEY", default="ug+cbde301nelb)(di0^p21osy3h=t$%2$-8d&0#xlyfj8&==5"
)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# TODO: We also use Postgres for tests now. So tests can only run in the fullstack setup.
# if not ADIT_FULLSTACK and sys.argv and ("test" in sys.argv or "pytest" in sys.argv[0]):
#     DATABASES = {"default": env.db("SQLITE_URL", default="sqlite:///./adit-sqlite.db")}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
    "debug_permissions",
    "django_extensions",
]

MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    # LoggingPanel does not work with Django Channels, see
    # https://github.com/django/channels/issues/1204
    # https://github.com/jazzband/django-debug-toolbar/issues/1300
    # "debug_toolbar.panels.logging.LoggingPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]


if env.bool("FORCE_DEBUG_TOOLBAR", default=False):
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG}

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

DICOM_DEBUG_LOGGER = False

INTERNAL_IPS = env.list("DJANGO_INTERNAL_IPS", default=["127.0.0.1"])

LOGGING["loggers"]["adit"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["celery"]["level"] = "DEBUG"  # noqa: F405

if env.bool("USE_DOCKER", default=False):
    import socket

    # For Debug Toolbar to show up on Docker Compose in development mode.
    # This only works when browsed from the host where the containers are run.
    # If viewed from somewhere else then DJANGO_INTERNAL_IPS must be set.
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]
