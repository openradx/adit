import datetime
import logging
import re
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO, Optional

from django.conf import settings
from pydicom import Dataset, dcmread, dcmwrite, valuerep

from adit.core.utils.sanitize import sanitize_filename

logger = logging.getLogger(__name__)

DateRange = tuple[datetime.date | None, datetime.date | None]
TimeRange = tuple[datetime.time | None, datetime.time | None]
DateTimeRange = tuple[datetime.datetime | None, datetime.datetime | None]


def write_dataset(ds: Dataset, fn: str | bytes | PathLike | BinaryIO) -> None:
    """Write a DICOM dataset to a file or buffer.

    This function is a wrapper around pydicom's dcmwrite function to make sure
    that the dataset is written in a consistent way.
    """
    dcmwrite(fn, ds, enforce_file_format=True)


def read_dataset(fp: str | bytes | PathLike | BinaryIO) -> Dataset:
    """Read a DICOM dataset from a file or buffer.

    This function is a wrapper around pydicom's dcmread function to make sure
    that the dataset is read in a consistent way.
    """
    return dcmread(fp, force=True)


def has_wildcards(value: str) -> bool:
    """Checks if a string has wildcards (according to the DICOM standard).

    https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_c.2.2.2.4.html
    """
    if "*" in value or "?" in value:
        return True
    return False


def convert_to_python_regex(value: str, case_sensitive=False) -> re.Pattern[str]:
    """Convert a DICOM wildcard string to a Python regex pattern.

    https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_c.2.2.2.4.html
    """
    value = re.escape(value)
    value = value.replace("\\*", ".*")
    value = value.replace("\\?", ".")

    flags = re.NOFLAG
    if not case_sensitive:
        flags |= re.IGNORECASE

    return re.compile(value, flags)


def person_name_to_dicom(value: str, add_wildcards=False) -> str:
    """Convert a person name to a DICOM compatible string representation.

    See also :func:`adit.core.templatetags.core_extras.person_name_to_dicom`
    """
    if add_wildcards:
        name = value.split(",")
        name = [s.strip() + "*" for s in name]
        return "^".join(name)

    return re.sub(r"\s*,\s*", "^", value)


def _build_date_time_datetime_range(
    start: str | datetime.date | datetime.time | datetime.datetime | None,
    end: str | datetime.date | datetime.time | datetime.datetime | None,
    vr_class: type[valuerep.DA] | type[valuerep.TM] | type[valuerep.DT],
):
    start_date = str(vr_class(start)) if start else ""
    end_date = str(vr_class(end)) if end else ""
    return f"{start_date}-{end_date}"


def _convert_to_dicom_date_time_datetime(
    value: Any,
    vr_class: type[valuerep.DA] | type[valuerep.TM] | type[valuerep.DT],
) -> str:
    """Convert a value to a DICOM compatible string representation.

    The value can be a string already in the DICOM format, but also a
    Python date, time, datetime object or a date, time, datetime range
    (tuple of two of them).
    """
    if isinstance(value, str):
        if "-" in value:
            range = [s.strip() for s in value.split("-")]
            if len(range) != 2:
                raise ValueError(f"Invalid range: {value}")
            start, end = range
            return _build_date_time_datetime_range(start, end, vr_class)
        else:
            return str(vr_class(value))
    elif isinstance(value, tuple):
        start, end = value
        return _build_date_time_datetime_range(start, end, vr_class)
    else:
        return str(vr_class(value))


def convert_to_dicom_date(value: str | datetime.date | DateRange) -> str:
    """Convert a date or date range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.DA)
    except ValueError:
        raise ValueError(f"Invalid date format: {value}")


def convert_to_dicom_time(value: str | datetime.time | TimeRange) -> str:
    """Convert a time or time range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.TM)
    except ValueError:
        raise ValueError(f"Invalid time format: {value}")


def convert_to_dicom_datetime(value: str | datetime.datetime | DateTimeRange) -> str:
    """Convert a datetime or datetime range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.DT)
    except ValueError:
        raise ValueError(f"Invalid datetime format: {value}")


def convert_to_python_date(value: str) -> datetime.date:
    """Convert a DICOM date string to a Python date object."""
    date_valuerep = valuerep.DA(value)
    assert date_valuerep is not None
    return datetime.date.fromisoformat(date_valuerep.isoformat())


def convert_to_python_time(value: str) -> datetime.time:
    """Convert a DICOM date string to a Python date object."""
    time_valuerep = valuerep.TM(value)
    assert time_valuerep is not None
    return datetime.time.fromisoformat(time_valuerep.isoformat())


def construct_download_file_path(
    ds: Dataset,
    download_folder: Path,
    patient_id: str,
    study_date: datetime.date,
    study_time: datetime.time,
    study_modalities: list[str],
    pseudonym: Optional[str] = None,
) -> Path:
    """Constructs the file path for a DICOM instance when transferring/downloading"""

    def _safe_path_component(raw_value: str) -> str:
        """Return a sanitized component that cannot trigger path traversal."""
        component = sanitize_filename(raw_value)
        if component in {".", ".."}:
            logger.warning(
                "Sanitized path component '%s' resolved to a disallowed segment; using fallback.",
                raw_value,
            )
            return "safe_path_placeholder"
        return component

    def _resolve_for_check(path: Path) -> Path:
        """Resolve a path for validation without altering the returned path."""
        if path.is_absolute():
            return path.resolve(strict=False)
        return (Path.cwd() / path).resolve(strict=False)

    # Determine the base patient folder
    patient_folder = download_folder / _safe_path_component(pseudonym or patient_id)

    # Handle modality filtering
    exclude_modalities = settings.EXCLUDE_MODALITIES
    modalities = study_modalities
    if pseudonym and exclude_modalities and study_modalities:
        included_modalities = [
            modality for modality in study_modalities if modality not in exclude_modalities
        ]
        modalities = included_modalities
    modalities_str = ",".join(modalities) if modalities else "UNKNOWN"
    # Build study folder path
    prefix = f"{study_date.strftime('%Y%m%d')}-{study_time.strftime('%H%M%S')}"
    study_folder = patient_folder / _safe_path_component(f"{prefix}-{modalities_str}")

    # Determine final folder based on series structure setting
    if settings.CREATE_SERIES_SUB_FOLDERS:
        series_number = ds.get("SeriesNumber")
        if not series_number:
            series_folder_name = ds.SeriesInstanceUID
        else:
            series_description = ds.get("SeriesDescription", "Undefined")
            series_folder_name = f"{series_number}-{_safe_path_component(series_description)}"
        series_folder_name = sanitize_filename(series_folder_name)
        final_folder = study_folder / series_folder_name
    else:
        final_folder = study_folder

    # Generate the final file path
    file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
    file_path = final_folder / file_name

    resolved_base_path = _resolve_for_check(download_folder)
    resolved_file_path = _resolve_for_check(file_path)
    if ".." in file_path.parts or not resolved_file_path.is_relative_to(resolved_base_path):
        raise ValueError(
            "Detected unsafe download path outside base folder '%s' for SOPInstanceUID '%s'.",
            download_folder,
            ds.SOPInstanceUID,
        )

    return file_path
