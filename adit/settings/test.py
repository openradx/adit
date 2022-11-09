from .development import *  # noqa: F403

if not DATABASES["default"]["NAME"].startswith("_test"):  # noqa: F405
    test_database = "test_" + DATABASES["default"]["NAME"]  # noqa: F405
    DATABASES["default"]["NAME"] = test_database  # noqa: F405
    DATABASES["default"]["TEST"] = {"NAME": test_database}  # noqa: F405

CELERY_TASK_DEFAULT_QUEUE = "test_queue"
CELERY_TASK_ROUTES = {}
