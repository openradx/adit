from .base import *
from .base import env

# Development settings

DEBUG = True

SECRET_KEY = env.str(
    'DJANGO_SECRET_KEY',
    default='ug+cbde301nelb)(di0^p21osy3h=t$%2$-8d&0#xlyfj8&==5'
)

ALLOWED_HOSTS = []

if sys.argv and ('test' in sys.argv or 'pytest' in sys.argv[0]):
    DATABASES = {'default': env.db('SQLITE_URL')}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

INSTALLED_APPS += ['debug_toolbar', 'django_extensions']

MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

DEBUG_TOOLBAR_CONFIG = {
    'DISABLE_PANELS': ['debug_toolbar.panels.redirects.RedirectsPanel'],
    'SHOW_TEMPLATE_CONTEXT': True,
}

CELERY_TASK_EAGER_PROPAGATES = True

INTERNAL_IPS = ['127.0.0.1']
if env.bool('USE_DOCKER', default=False):
    import socket
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += ['.'.join(ip.split('.')[:-1] + ['1']) for ip in ips]
