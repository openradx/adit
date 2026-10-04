import uuid
from datetime import date
from pathlib import Path

import pytest
from pydicom import Dataset
from pydicom import config as pydicom_config
from pydicom.dataset import FileMetaDataset
from pydicom.uid import UID, CTImageStorage, ExplicitVRLittleEndian, generate_uid

from adit.core.utils.dicom_utils import write_dataset
from adit.core.utils.series_filters import FilterSpec, select_study_series
from adit.core.utils.testing_helpers import load_sample_dicoms
from adit.router.utils import batches, spool
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


def _minimal_dataset(
    *,
    sop_instance_uid: str,
    series_instance_uid: str,
    study_instance_uid: str,
    modality: str,
    patient_id: str = "",
    study_description: str = "",
    patient_birth_date: str = "",
    study_date: str = "",
) -> Dataset:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = sop_instance_uid
    ds.SeriesInstanceUID = series_instance_uid
    ds.StudyInstanceUID = study_instance_uid
    ds.Modality = modality
    ds.PatientID = patient_id
    ds.StudyDescription = study_description
    ds.PatientBirthDate = patient_birth_date
    ds.StudyDate = study_date
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = UID(sop_instance_uid)
    return ds


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


def test_study_facts_come_from_any_header_that_has_them(spool_root):
    study_uid = generate_uid()
    sr_series_uid = generate_uid()
    ct_series_uid = generate_uid()
    # The lowest SOP Instance UID sorts first and is read first; it lacks the fields
    # a conformant derived object (here an SR) may legitimately omit or leave empty.
    sparse = _minimal_dataset(
        sop_instance_uid="1.2.1",
        series_instance_uid=sr_series_uid,
        study_instance_uid=study_uid,
        modality="SR",
        study_date="20261001",
    )
    full = _minimal_dataset(
        sop_instance_uid="1.2.2",
        series_instance_uid=ct_series_uid,
        study_instance_uid=study_uid,
        modality="CT",
        patient_id="1001",
        study_description="CT head",
        patient_birth_date="20000101",
        study_date="20261001",
    )
    path = _batch(spool_root, [sparse, full])

    contents = read_batch(spool_root, path, TODAY)

    assert contents.patient_id == "1001"
    assert contents.study.StudyDescription == "CT head"
    assert contents.study.PatientBirthDate == date(2000, 1, 1)

    rule_filter = FilterSpec(modality="CT", study_description="CT head", min_age=20, max_age=30)
    selected = select_study_series(contents.study, contents.series, [rule_filter])
    assert {s.series_instance_uid for s in selected} == {ct_series_uid}


def test_header_read_oserror_is_not_quarantined(spool_root, mocker):
    datasets = list(load_sample_dicoms("1004"))[:1]
    path = _batch(spool_root, datasets)
    mocker.patch.object(batches, "dcmread", side_effect=OSError("Simulated I/O error."))

    with pytest.raises(OSError):
        read_batch(spool_root, path, TODAY)

    assert [p.name for p in path.iterdir()] == [f"{datasets[0].SOPInstanceUID}.dcm"]
    assert list((spool_root / spool.QUARANTINE).iterdir()) == []


def test_series_instance_uid_that_is_too_long_is_quarantined(spool_root):
    # pydicom's own UID validation also warns on a value this invalid, which the test
    # suite's filterwarnings turns into an error; disabling it isolates read_batch's
    # own is_valid_uid check (the thing this test pins) from that unrelated warning.
    datasets = list(load_sample_dicoms("1004"))[:1]
    with pydicom_config.disable_value_validation():
        datasets[0].SeriesInstanceUID = "9" * 65
        path = _batch(spool_root, datasets)

        contents = read_batch(spool_root, path, TODAY)

    assert contents.images == []
    qdir = spool_root / spool.QUARANTINE / "20261004"
    assert len(list(qdir.iterdir())) == 1


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
