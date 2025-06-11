import datetime
import logging
import re
from os import PathLike
from typing import Any, BinaryIO

from pydicom import Dataset, dcmread, dcmwrite, valuerep

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
