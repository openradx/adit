import io
import os
import tempfile
from typing import Any, Dict, Iterable

import pytest
from django.conf import settings

from adit.core.utils.dicom_utils import read_dataset

# Workaround to make playwright work with Django
# see https://github.com/microsoft/playwright-pytest/issues/29#issuecomment-731515676
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def uploadable_test_dicoms():
    def _test_dicoms(patient_id: str) -> Iterable[Dict[str, Any | str | bytes]]:
        test_dicoms_path = settings.BASE_DIR / "samples" / "dicoms" / patient_id
        for root, _, files in os.walk(test_dicoms_path):
            if len(files) != 0:
                for file in files:
                    try:
                        ds = read_dataset(os.path.join(root, file))
                        buffer = io.BytesIO()
                        ds.save_as(buffer)
                    except Exception:
                        continue
                    yield {
                        "name": ds.SOPInstanceUID,
                        "mimeType": "text/plain",
                        "buffer": buffer.getvalue(),
                    }

    return _test_dicoms


@pytest.fixture
def provide_path_to_file_dir():
    def _test_dicoms(patient_id: str) -> Iterable[str]:
        test_dicoms_path = settings.BASE_DIR / "samples" / "dicoms" / patient_id
        folders = os.listdir(test_dicoms_path)
        for folder in folders:
            yield os.path.join(test_dicoms_path, folder)

    return _test_dicoms


@pytest.fixture
def noncompatible_test_file():
    def _noncompatible_file():
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
            tmp_file.write(b"This is a test text file.")
            tmp_file.seek(0)

        return os.path.dirname(tmp_file.name)

    return _noncompatible_file
