from .development import *  # noqa: F403

EXAMPLE_APP = True

INSTALLED_APPS += [  # noqa: F405
    "adit.core.tests.example_app.apps.ExampleAppConfig",
]

# We must force our background workers that a started during integration tests as
# a subprocess to use the test database.
if not DATABASES["default"]["NAME"].startswith("test_"):  # noqa: F405
    test_database = "test_" + DATABASES["default"]["NAME"]  # noqa: F405
    DATABASES["default"]["NAME"] = test_database  # noqa: F405
    DATABASES["default"]["TEST"] = {"NAME": test_database}  # noqa: F405

# This test worker uses a "test_queue" (see adit_celery_worker fixture). In contrast
# to development and production system we only use one worker that handles all
# Celery tasks.
CELERY_TASK_DEFAULT_QUEUE = "test_queue"
CELERY_TASK_ROUTES = {}

DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}
