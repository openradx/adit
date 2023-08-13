import datetime
import logging
import re
from typing import Any, Iterable, Literal

from pydicom import DataElement, Dataset, config, datadict, valuerep

logger = logging.getLogger(__name__)


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


DateRange = tuple[datetime.date | None, datetime.date | None]
TimeRange = tuple[datetime.time | None, datetime.time | None]
DateTimeRange = tuple[datetime.datetime | None, datetime.datetime | None]


def _build_date_time_range(
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
            start, end = value.split("-")
            return _build_date_time_range(start, end, vr_class)
        else:
            return str(vr_class(value))
    elif isinstance(value, tuple):
        start, end = value
        return _build_date_time_range(start, end, vr_class)
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
    return datetime.date.fromisoformat(valuerep.DA(value).isoformat())


def convert_to_python_time(value: str) -> datetime.time:
    """Convert a DICOM date string to a Python date object."""
    return datetime.time.fromisoformat(valuerep.TM(value).isoformat())


def convert_to_python_datetime(value: str) -> datetime.datetime:
    """Convert a DICOM date string to a Python date object."""
    return datetime.datetime.fromisoformat(valuerep.DT(value).isoformat())


def ensure_elements(ds: Dataset, *keywords: str) -> None:
    """Ensure that specific elements in a dataset are present."""
    for keyword in keywords:
        if keyword not in ds:
            setattr(ds, keyword, "")


class _NoValue:
    pass


def _set_dataset_value(
    ds: Dataset, k: str, v: Any, ignore_invalid_tags=False, ignore_invalid_values=False
) -> None:
    t = datadict.tag_for_keyword(k)
    if t is None:
        if ignore_invalid_tags:
            return
        raise ValueError(f"Unknown DICOM tag with keyword: {k}")

    vr = datadict.dictionary_VR(t)

    try:
        if v is None:
            setattr(ds, k, "")
        elif vr == "DA":
            date = convert_to_python_date(v)
            setattr(ds, k, date)
        elif vr == "DT":
            time = convert_to_python_time(v)
            setattr(ds, k, time)
        elif vr == "TM":
            datetime = convert_to_python_datetime(v)
            setattr(ds, k, datetime)
        else:
            elem = DataElement(t, vr, v, validation_mode=config.RAISE)
            ds.add(elem)
    except ValueError as err:
        if not ignore_invalid_values:
            raise ValueError(f"Invalid value for DICOM tag {t} ({vr}): {v}") from err


def create_query_dataset(
    *,
    QueryRetrieveLevel: Literal["PATIENT", "STUDY", "SERIES", "IMAGE"] | type[_NoValue] = _NoValue,
    PatientID: str | type[_NoValue] = _NoValue,
    PatientName: str | type[_NoValue] = _NoValue,
    PatientBirthDate: str | datetime.date | DateRange | type[_NoValue] | None = _NoValue,
    StudyInstanceUID: str | type[_NoValue] = _NoValue,
    AccessionNumber: str | type[_NoValue] = _NoValue,
    StudyDescription: str | type[_NoValue] = _NoValue,
    StudyDate: str | datetime.date | DateRange | type[_NoValue] | None = _NoValue,
    StudyTime: str | datetime.time | TimeRange | type[_NoValue] | None = _NoValue,
    ModalitiesInStudy: str | type[_NoValue] = _NoValue,  # Currently we allow only one modality
    SeriesInstanceUID: str | type[_NoValue] = _NoValue,
    SeriesDescription: str | type[_NoValue] = _NoValue,
    SeriesNumber: int | type[_NoValue] = _NoValue,
    Modality: str | type[_NoValue] = _NoValue,
) -> Dataset:
    """A helper function for type hinting query parameters."""
    ds = Dataset()

    for k, v in locals().items():
        if k == "ds":
            continue

        if v is _NoValue:
            continue

        _set_dataset_value(ds, k, v)

    return ds


def convert_query_dict_to_dataset(query: dict[str, str], **additional_attributes) -> Dataset:
    ds = Dataset()

    for k, v in query.items():
        _set_dataset_value(ds, k, v, ignore_invalid_tags=True, ignore_invalid_values=True)

    for k, v in additional_attributes.items():
        _set_dataset_value(ds, k, v)

    return ds


def create_dicomweb_query(ds: Dataset) -> dict[str, str]:
    """Create DICOMweb compatible query dict.

    Convert a query dataset to a DICOMweb compatible query dict.
    Returns a new dict, the original dataset is not modified.
    """
    query = {}
    for elem in ds:
        key = elem.keyword
        val = elem.value
        vr = elem.VR

        if elem.tag.is_private:
            continue

        if elem.tag == (0x7FE0, 0x0010):
            raise ValueError("PixelData is not allowed in DICOMweb queries.")

        if vr == "SQ":
            raise ValueError("Sequence elements are not allowed in DICOMweb queries.")

        if val in ("*", "?", None):
            query[key] = ""
        elif isinstance(val, Iterable):
            query[key] = ",".join(val)
        else:
            # VR of DA, TM, DT are already in string format
            query[elem.keyword] = str(val).replace("\u0000", "").strip()

    return query
