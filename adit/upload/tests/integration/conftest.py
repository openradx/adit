import os
import tempfile
from typing import Iterator

import pytest

# Workaround to make playwright work with Django
# see https://github.com/microsoft/playwright-pytest/issues/29#issuecomment-731515676
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def invalid_sample_files_folder() -> Iterator[str]:
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
        tmp_file.write(b"This is not DICOM data.")
        tmp_file.seek(0)
        yield os.path.dirname(tmp_file.name)
