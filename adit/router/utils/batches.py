"""Reads the headers of the images in a closed router batch."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from pydicom import Dataset, dcmread

from adit.core.utils.dicom_utils import convert_to_python_date, convert_to_python_time
from adit.core.utils.series_filters import DiscoveredSeries

from . import spool

logger = logging.getLogger(__name__)

_REQUIRED_UIDS = ("SOPInstanceUID", "SeriesInstanceUID", "StudyInstanceUID")


@dataclass(frozen=True)
class SpooledImage:
    path: Path
    sop_instance_uid: str
    series_instance_uid: str


@dataclass(frozen=True)
class BatchStudy:
    """The study-level facts of a batch (a StudyFacts), read from its headers."""

    ModalitiesInStudy: list[str]
    StudyDescription: str
    PatientBirthDate: date | None
    StudyDate: date | None


@dataclass(frozen=True)
class BatchContents:
    patient_id: str
    study_instance_uid: str
    study: BatchStudy
    series: list[DiscoveredSeries]
    images: list[SpooledImage]


def read_batch(spool_root: Path, batch_path: Path, today: date) -> BatchContents:
    """Read the headers of a batch. Files that can't be read move to the quarantine."""
    headers: list[tuple[Path, Dataset]] = []
    for path in sorted(p for p in batch_path.iterdir() if p.is_file()):
        try:
            headers.append((path, _read_header(path)))
        except Exception:
            logger.warning(
                "Moving unreadable file %s to the router quarantine.",
                path,
                exc_info=True,
            )
            spool.quarantine_file(spool_root, path, today)

    if not headers:
        return BatchContents("", "", BatchStudy([], "", None, None), [], [])

    first = headers[0][1]
    birth_date = _parse_date(first.get("PatientBirthDate"), "PatientBirthDate", batch_path)
    study_date = _parse_date(first.get("StudyDate"), "StudyDate", batch_path)
    study_time = _parse_time(first.get("StudyTime"))
    # The age needs both dates; without a study date it counts as unknown.
    series_birth_date = birth_date if study_date else None
    study_datetime = datetime.combine(study_date or date.min, study_time or time())

    by_series: dict[str, list[Dataset]] = {}
    for _, ds in headers:
        by_series.setdefault(str(ds.SeriesInstanceUID), []).append(ds)

    series: list[DiscoveredSeries] = []
    for series_uid, datasets in by_series.items():
        ds = datasets[0]
        series.append(
            DiscoveredSeries(
                patient_id=str(first.get("PatientID", "")),
                accession_number=str(first.get("AccessionNumber", "")),
                study_instance_uid=str(first.StudyInstanceUID),
                series_instance_uid=series_uid,
                modality=str(ds.get("Modality", "")),
                study_description=str(first.get("StudyDescription", "")),
                series_description=str(ds.get("SeriesDescription", "")),
                series_number=_parse_int(ds.get("SeriesNumber")),
                study_datetime=study_datetime,
                institution_name=str(ds.get("InstitutionName", "")),
                number_of_images=len(datasets),
                patient_birth_date=series_birth_date,
            )
        )

    return BatchContents(
        patient_id=str(first.get("PatientID", "")),
        study_instance_uid=str(first.StudyInstanceUID),
        study=BatchStudy(
            ModalitiesInStudy=sorted({s.modality for s in series if s.modality}),
            StudyDescription=str(first.get("StudyDescription", "")),
            PatientBirthDate=birth_date,
            StudyDate=study_date,
        ),
        series=series,
        images=[
            SpooledImage(path, str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID))
            for path, ds in headers
        ],
    )


def read_series_images(batch_path: Path, series_uids: set[str]) -> list[SpooledImage]:
    images: list[SpooledImage] = []
    for path in sorted(p for p in batch_path.iterdir() if p.is_file()):
        ds = dcmread(path, stop_before_pixels=True)
        if str(ds.SeriesInstanceUID) in series_uids:
            images.append(SpooledImage(path, str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID)))
    return images


def _read_header(path: Path) -> Dataset:
    ds = dcmread(path, stop_before_pixels=True)
    for keyword in _REQUIRED_UIDS:
        if not ds.get(keyword):
            raise ValueError(f"{keyword} is missing.")
    return ds


def _parse_date(value: object, keyword: str, batch_path: Path) -> date | None:
    if not value:
        return None
    try:
        return convert_to_python_date(str(value))
    except ValueError:
        logger.warning("Ignoring the invalid %s %r of router batch %s.", keyword, value, batch_path)
        return None


def _parse_time(value: object) -> time | None:
    if not value:
        return None
    try:
        return convert_to_python_time(str(value))
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    try:
        return int(str(value))
    except ValueError:
        return None
