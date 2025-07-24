from pathlib import Path

from .base import *  # noqa: F403

DEBUG = False

EXAMPLE_APP = True

INSTALLED_APPS += [  # noqa: F405
    "adit.core.tests.example_app.apps.ExampleAppConfig",
]

# The base directory of the project (the root of the repository)
BASE_PATH = Path(__file__).resolve(strict=True).parent.parent.parent

# Path to sample DICOM files, used only for testing purposes.
DICOM_SAMPLE_DIR = str(BASE_PATH / "samples" / "dicoms")

# We must force our background workers that a started during acceptance tests as
# a subprocess to use the test database.
if not DATABASES["default"]["NAME"].startswith("test_"):  # noqa: F405
    test_database = "test_" + DATABASES["default"]["NAME"]  # noqa: F405
    DATABASES["default"]["NAME"] = test_database  # noqa: F405
    DATABASES["default"]["TEST"] = {"NAME": test_database}  # noqa: F405

DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}
