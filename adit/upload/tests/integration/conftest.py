import io
import os
from pathlib import Path
from typing import Iterable

import pytest
from django.conf import settings
from pydicom import Dataset

from adit.core.utils.dicom_utils import read_dataset

# Workaround to make playwright work with Django
# see https://github.com/microsoft/playwright-pytest/issues/29#issuecomment-731515676
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def uploadable_test_dicoms():
    def _test_dicoms(patient_id: str) -> Iterable[Dataset]:
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
def test_dicom_paths():
    def _test_dicom_paths(patient_id: str) -> list[Path]:
        paths = []
        for root, _, files in os.walk(settings.BASE_DIR / "samples" / "dicoms" / patient_id):
            if len(files) != 0:
                for file in files:
                    if file.endswith((".dcm", ".DCM")):
                        paths.append(os.path.join(root, file))
        return paths

    return _test_dicom_paths
