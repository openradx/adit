import datetime
from datetime import date, time
from typing import Any, Iterable, Literal

from pydicom import DataElement, Dataset, config, datadict, valuerep

DateRange = tuple[datetime.date | None, datetime.date | None]
TimeRange = tuple[datetime.time | None, datetime.time | None]
DateTimeRange = tuple[datetime.datetime | None, datetime.datetime | None]


class BaseDataset:
    def __init__(self, ds: Dataset) -> None:
        self._ds = ds

    @property
    def PatientID(self) -> str:
        return str(self._ds.PatientID)

    @property
    def PatientName(self) -> str:
        return str(self._ds.PatientName)

    @property
    def PatientBirthDate(self) -> date:
        birth_date = self._ds.PatientBirthDate
        return _convert_to_python_date(birth_date)

    @property
    def PatientSex(self) -> Literal["M", "F", "O"]:
        return str(self._ds.PatientSex)  # type: ignore

    @property
    def NumberOfPatientRelatedStudies(self) -> int:
        return int(self._ds.NumberOfPatientRelatedStudies)

    @property
    def StudyInstanceUID(self) -> str:
        return str(self._ds.StudyInstanceUID)

    @property
    def AccessionNumber(self) -> str:
        return str(self._ds.AccessionNumber)

    @property
    def StudyDate(self) -> date:
        study_date = self._ds.StudyDate
        return _convert_to_python_date(study_date)

    @property
    def StudyTime(self) -> time:
        study_time = self._ds.StudyTime
        return _convert_to_python_time(study_time)

    @property
    def StudyDescription(self) -> str:
        return str(self._ds.StudyDescription)

    @property
    def ModalitiesInStudy(self) -> list[str]:
        modalities = self._ds.ModalitiesInStudy
        # Cave, in Python string are also iterable, so we test it first
        if isinstance(modalities, str):
            return [modalities]
        if isinstance(modalities, Iterable):
            return [str(modality) for modality in modalities]
        return []

    @property
    def NumberOfStudyRelatedSeries(self) -> int:
        return int(self._ds.NumberOfStudyRelatedSeries)

    @property
    def NumberOfStudyRelatedInstances(self) -> int:
        return int(self._ds.NumberOfStudyRelatedInstances)

    @property
    def SeriesInstanceUID(self) -> str:
        return str(self._ds.SeriesInstanceUID)

    @property
    def SeriesDescription(self) -> str:
        return str(self._ds.SeriesDescription)

    @property
    def SeriesNumber(self) -> int:
        return int(self._ds.SeriesNumber)

    @property
    def Modality(self) -> str:
        return str(self._ds.Modality)

    @property
    def NumberOfSeriesRelatedInstances(self) -> int:
        return int(self._ds.NumberOfSeriesRelatedInstances)

    @property
    def SOPInstanceUID(self) -> str:
        return str(self._ds.SOPInstanceUID)

    @property
    def InstanceNumber(self) -> int:
        return int(self._ds.InstanceNumber)

    @property
    def InstanceAvailability(self) -> Literal["ONLINE", "OFFLINE", "NEARLINE", "UNAVAILABLE"]:
        return str(self._ds.InstanceAvailability)  # type: ignore

    @property
    def dataset(self) -> Dataset:
        return self._ds

    def get(self, keyword: str, default: Any | None = None) -> Any:
        return self._ds.get(keyword, default)

    def __repr__(self) -> str:
        return str(self._ds)


class _NoValue:
    pass


class QueryDataset(BaseDataset):
    def ensure_elements(self, *keywords: str) -> None:
        """Ensure that specific elements in a dataset are present."""
        for keyword in keywords:
            if keyword not in self._ds:
                setattr(self._ds, keyword, "")

    @property
    def QueryRetrieveLevel(self) -> Literal["PATIENT", "STUDY", "SERIES", "IMAGE"]:
        return str(self._ds.QueryRetrieveLevel)  # type: ignore

    @QueryRetrieveLevel.setter
    def QueryRetrieveLevel(self, value: Literal["PATIENT", "STUDY", "SERIES", "IMAGE"]) -> None:
        self._ds.QueryRetrieveLevel = value

    @property
    def dataset(self) -> Dataset:
        return self._ds

    def has(self, keyword: str) -> bool:
        """Checks that the key exists in the dataset and is not empty."""
        v = self._ds.get(keyword, None)
        return bool(v)

    @classmethod
    def create(
        cls,
        *,
        QueryRetrieveLevel: Literal["PATIENT", "STUDY", "SERIES", "IMAGE"]
        | type[_NoValue] = _NoValue,
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
        SeriesNumber: int | str | type[_NoValue] = _NoValue,
        Modality: str | type[_NoValue] = _NoValue,
    ) -> "QueryDataset":
        """A helper factory method for type hinting query parameters."""
        ds = Dataset()

        for k, v in locals().items():
            if k == "cls" or k == "ds":
                continue

            if v is _NoValue:
                continue

            _set_dataset_value(ds, k, v)

        return QueryDataset(ds)

    @classmethod
    def from_dict(cls, query: dict[str, str], **additional_attributes) -> "QueryDataset":
        ds = Dataset()

        for k, v in query.items():
            _set_dataset_value(ds, k, v, ignore_invalid_tags=True, ignore_invalid_values=True)

        for k, v in additional_attributes.items():
            _set_dataset_value(ds, k, v)

        return QueryDataset(ds)

    def dictify(self) -> dict[str, str]:
        """Create DICOMweb compatible query dict.

        Convert a query dataset to a DICOMweb compatible query dict.
        Returns a new dict, the original dataset is not modified.
        """
        query = {}
        for elem in self._ds:
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
            elif not isinstance(val, str) and isinstance(val, Iterable):
                query[key] = ",".join(val)
            else:
                # VR of DA, TM, DT are already in string format
                query[elem.keyword] = str(val).replace("\u0000", "").strip()

        return query


class ResultDataset(BaseDataset):
    @BaseDataset.ModalitiesInStudy.setter
    def ModalitiesInStudy(self, value: str | list[str]) -> None:
        self._ds.ModalitiesInStudy = value

    def __contains__(self, keyword: str) -> bool:
        return keyword in self._ds


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
            date = _convert_to_dicom_date(v)
            setattr(ds, k, date)
        elif vr == "DT":
            time = _convert_to_dicom_time(v)
            setattr(ds, k, time)
        elif vr == "TM":
            datetime = _convert_to_dicom_datetime(v)
            setattr(ds, k, datetime)
        else:
            elem = DataElement(t, vr, v, validation_mode=config.RAISE)
            ds.add(elem)
    except ValueError as err:
        if not ignore_invalid_values:
            raise ValueError(f"Invalid value for DICOM tag {t} ({vr}): {v}") from err


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


def _convert_to_dicom_date(value: str | datetime.date | DateRange) -> str:
    """Convert a date or date range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.DA)
    except ValueError:
        raise ValueError(f"Invalid date format: {value}")


def _convert_to_dicom_time(value: str | datetime.time | TimeRange) -> str:
    """Convert a time or time range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.TM)
    except ValueError:
        raise ValueError(f"Invalid time format: {value}")


def _convert_to_dicom_datetime(value: str | datetime.datetime | DateTimeRange) -> str:
    """Convert a datetime or datetime range to a DICOM compatible string representation."""
    try:
        return _convert_to_dicom_date_time_datetime(value, valuerep.DT)
    except ValueError:
        raise ValueError(f"Invalid datetime format: {value}")


def _convert_to_python_date(value: str) -> datetime.date:
    """Convert a DICOM date string to a Python date object."""
    return datetime.date.fromisoformat(valuerep.DA(value).isoformat())


def _convert_to_python_time(value: str) -> datetime.time:
    """Convert a DICOM date string to a Python date object."""
    return datetime.time.fromisoformat(valuerep.TM(value).isoformat())
