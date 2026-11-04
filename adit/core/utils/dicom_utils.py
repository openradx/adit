import datetime
import logging
import re
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO

from django.conf import settings
from pydicom import Dataset, dcmread, dcmwrite, valuerep

from adit.core.utils.sanitize import sanitize_filename

logger = logging.getLogger(__name__)

DateRange = tuple[datetime.date | None, datetime.date | None]
TimeRange = tuple[datetime.time | None, datetime.time | None]
DateTimeRange = tuple[datetime.datetime | None, datetime.datetime | None]
DateTimeVR = type[valuerep.DA] | type[valuerep.TM] | type[valuerep.DT]


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


def convert_to_python_regex(value: str, case_insensitive=False) -> re.Pattern[str]:
    """Convert a DICOM wildcard string to a Python regex pattern.

    DICOM Wild Card Matching is whole-value, so callers must use
    ``.fullmatch()`` (not ``.search()``) on the returned pattern.

    https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_c.2.2.2.4.html
    """
    value = re.escape(value)
    value = value.replace("\\*", ".*")
    value = value.replace("\\?", ".")

    flags = re.NOFLAG
    if case_insensitive:
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


def _parse_date_time_datetime(
    value: str | datetime.date | datetime.time | datetime.datetime | None,
    vr_class: DateTimeVR,
) -> valuerep.DA | valuerep.TM | valuerep.DT | None:
    """Parse a value, an empty or blank one yields None."""
    return vr_class(value.strip() if isinstance(value, str) else value)


def _build_date_time_datetime_range(
    start: str | datetime.date | datetime.time | datetime.datetime | None,
    end: str | datetime.date | datetime.time | datetime.datetime | None,
    vr_class: DateTimeVR,
) -> str:
    start_value = _parse_date_time_datetime(start, vr_class)
    end_value = _parse_date_time_datetime(end, vr_class)

    # A bare "-" is not a valid range; no bounds at all is a universal match.
    if start_value is None and end_value is None:
        return ""

    # PS3.4 C.2.2.2.5 only defines a range whose start is less or equal to its end. A
    # reversed one is accepted by most SCPs but silently matches nothing.
    if start_value is not None and end_value is not None:
        try:
            is_reversed = start_value > end_value  # type: ignore[operator]
        except TypeError as err:
            raise ValueError("Range mixes bounds with and without a UTC offset") from err
        if is_reversed:
            raise ValueError(f"Range start {start_value} is after its end {end_value}")

    return "-".join("" if v is None else str(v) for v in (start_value, end_value))


def _convert_to_dicom_date_time_datetime(value: Any, vr_class: DateTimeVR) -> str:
    """Convert a value to a DICOM compatible string representation.

    The value can be a string already in the DICOM format, but also a
    Python date, time, datetime object or a date, time, datetime range
    (tuple of two of them). An empty value or range becomes the universal
    match "", and a range must not end before it starts (PS3.4 C.2.2.2.5).
    As every "-" of a string separates a range, a DT string must not have
    a negative UTC offset.
    """
    if isinstance(value, str):
        parts = [s.strip() for s in value.split("-")]
        if len(parts) > 2:
            raise ValueError(f"Invalid range: {value}")
        if len(parts) == 2:
            return _build_date_time_datetime_range(parts[0], parts[1], vr_class)
        value = parts[0]
    elif isinstance(value, tuple):
        start, end = value
        return _build_date_time_datetime_range(start, end, vr_class)

    parsed = _parse_date_time_datetime(value, vr_class)
    return "" if parsed is None else str(parsed)


def convert_to_dicom_date(value: str | datetime.date | DateRange) -> str:
    """Convert a date or date range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.DA)
    except ValueError as err:
        raise ValueError(f"Invalid date format: {value} ({err})") from err


def convert_to_dicom_time(value: str | datetime.time | TimeRange) -> str:
    """Convert a time or time range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.TM)
    except ValueError as err:
        raise ValueError(f"Invalid time format: {value} ({err})") from err


def convert_to_dicom_datetime(value: str | datetime.datetime | DateTimeRange) -> str:
    """Convert a datetime or datetime range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.DT)
    except ValueError as err:
        raise ValueError(f"Invalid datetime format: {value} ({err})") from err


def convert_to_python_date(value: str) -> datetime.date:
    """Convert a DICOM date string to a Python date object.

    Raises ValueError if the value is empty or invalid.
    """
    date_valuerep = valuerep.DA(value)
    if date_valuerep is None:
        raise ValueError(f"Empty DICOM date: {value!r}")
    return datetime.date.fromisoformat(date_valuerep.isoformat())


def convert_to_python_time(value: str) -> datetime.time:
    """Convert a DICOM time string to a Python time object.

    Raises ValueError if the value is empty or invalid.
    """
    time_valuerep = valuerep.TM(value)
    if time_valuerep is None:
        raise ValueError(f"Empty DICOM time: {value!r}")
    return datetime.time.fromisoformat(time_valuerep.isoformat())


def construct_download_file_path(
    ds: Dataset,
    download_folder: Path,
    patient_id: str,
    study_date: datetime.date,
    study_time: datetime.time,
    study_modalities: list[str],
    pseudonym: str | None = None,
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
            return "safe_default"
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
        final_folder = study_folder / series_folder_name
    else:
        final_folder = study_folder

    # Generate the final file path
    file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
    file_path = final_folder / file_name

    resolved_file_path = _resolve_for_check(file_path)
    resolved_base_path = _resolve_for_check(download_folder)

    if not resolved_file_path.is_relative_to(resolved_base_path):
        raise ValueError(
            f"Detected unsafe download path outside base folder '{download_folder}' "
            f"for SOPInstanceUID '{ds.SOPInstanceUID}'."
        )

    return file_path
