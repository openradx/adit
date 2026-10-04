import uuid
from datetime import date
from pathlib import Path

import pytest
from pydicom import Dataset

from adit.core.utils.dicom_utils import write_dataset
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.utils import spool
from adit.router.utils.batches import read_batch, read_series_images

TODAY = date(2026, 10, 4)


@pytest.fixture
def spool_root(tmp_path: Path) -> Path:
    spool.ensure_spool_dirs(tmp_path)
    return tmp_path


def _batch(spool_root: Path, datasets: list[Dataset]) -> Path:
    path = spool.batch_dir(spool_root, 7, uuid.uuid4())
    path.mkdir(parents=True)
    for ds in datasets:
        write_dataset(ds, path / f"{ds.SOPInstanceUID}.dcm")
    return path


def test_batch_contents_describe_the_study(spool_root):
    datasets = list(load_sample_dicoms("1001"))  # three CT series (2, 4, 4 images), one SR
    path = _batch(spool_root, datasets)

    contents = read_batch(spool_root, path, TODAY)

    assert contents.patient_id == "1001"
    assert contents.study_instance_uid == str(datasets[0].StudyInstanceUID)
    assert len(contents.images) == len(datasets)
    assert contents.study.ModalitiesInStudy == ["CT", "SR"]
    assert contents.study.PatientBirthDate == date(1945, 4, 27)
    assert sorted((s.modality, s.number_of_images) for s in contents.series) == [
        ("CT", 2),
        ("CT", 4),
        ("CT", 4),
        ("SR", 1),
    ]


def test_unreadable_files_go_to_the_quarantine(spool_root):
    datasets = list(load_sample_dicoms("1004"))[:2]
    path = _batch(spool_root, datasets)
    (path / "broken.dcm").write_bytes(b"not dicom")
    no_uid = datasets[0].copy()
    del no_uid.SOPInstanceUID
    write_dataset(no_uid, path / "no-uid.dcm")

    contents = read_batch(spool_root, path, TODAY)

    assert len(contents.images) == 2
    qdir = spool_root / spool.QUARANTINE / "20261004"
    quarantined = sorted(p.name.split("_", 1)[1] for p in qdir.iterdir())
    assert quarantined == ["broken.dcm", "no-uid.dcm"]


def test_missing_birth_date_leaves_the_age_unknown(spool_root):
    datasets = list(load_sample_dicoms("1004"))[:1]
    del datasets[0].PatientBirthDate
    path = _batch(spool_root, datasets)

    contents = read_batch(spool_root, path, TODAY)

    assert contents.study.PatientBirthDate is None
    assert contents.series[0].patient_birth_date is None


def test_missing_study_date_leaves_the_age_unknown(spool_root):
    datasets = list(load_sample_dicoms("1004"))[:1]
    datasets[0].StudyDate = ""
    path = _batch(spool_root, datasets)

    contents = read_batch(spool_root, path, TODAY)

    assert contents.study.StudyDate is None
    assert contents.series[0].patient_birth_date is None


def test_read_series_images_lists_only_the_requested_series(spool_root):
    datasets = list(load_sample_dicoms("1001"))
    path = _batch(spool_root, datasets)
    ct_series = {str(ds.SeriesInstanceUID) for ds in datasets if ds.Modality == "CT"}

    images = read_series_images(path, ct_series)

    assert len(images) == 10
    assert {image.series_instance_uid for image in images} == ct_series
