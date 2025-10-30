import os
import tempfile
from typing import Iterator
from unittest.mock import patch

import pytest
from asgiref.sync import AsyncToSync

# Workaround to make playwright work with Django
# see https://github.com/microsoft/playwright-pytest/issues/29#issuecomment-731515676
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def invalid_sample_files_folder() -> Iterator[str]:
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
        tmp_file.write(b"This is not DICOM data.")
        tmp_file.seek(0)
        yield os.path.dirname(tmp_file.name)


@pytest.fixture(autouse=True)
def force_new_event_loop():
    """Fix for tests using the LiveServer and Playwright introduced by asgiref > 3.9.0.
    This patch forces AsyncToSync to always force a new event loop, which avoids issues with
    deadlocks in tests."""
    original_init = AsyncToSync.__init__

    def patched_init(self, awaitable, force_new_loop: bool = False):
        original_init(self, awaitable, force_new_loop=True)

    with patch.object(AsyncToSync, "__init__", patched_init):
        yield
