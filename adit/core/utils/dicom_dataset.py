import datetime
import logging
from datetime import date, time
from typing import Any, Iterable, Literal

from pydicom import DataElement, Dataset, datadict

from .dicom_utils import (
    DateRange,
    TimeRange,
    convert_to_dicom_date,
    convert_to_dicom_datetime,
    convert_to_dicom_time,
    convert_to_python_date,
    convert_to_python_time,
)

logger = logging.getLogger(__name__)


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
    def PatientBirthDate(self) -> date | None:
        try:
            birth_date = self._ds.PatientBirthDate
            return convert_to_python_date(birth_date)
        except Exception:
            # Birth date can be absent on some external images even if it
            # is mandatory by the DICOM standard
            logger.exception(f"Invalid patient birth date in dataset:\n{self._ds}")
            return None

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
        return convert_to_python_date(study_date)

    @property
    def StudyTime(self) -> time:
        study_time = self._ds.StudyTime
        return convert_to_python_time(study_time)

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
    def SeriesNumber(self) -> int | None:
        series_number = self._ds.SeriesNumber
        return int(series_number) if series_number is not None else None

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
        """Ensure that specific elements in a dataset are present (even if empty)."""
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
            _set_dataset_value(ds, k, v)

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

    def get_search_filters_and_fields(self) -> tuple[dict[str, str], list[str]]:
        """Create python dicomweb-client compatible search filters and fields.

        Convert a query dataset to python dicomweb-client compatible search filters and fields.
        Removes empty or none values for search filters but keeps all keys as search fields.
        Returns a new dict and list, the original dataset is not modified.
        """

        query_dict = self.dictify()
        search_filters = {k: v for k, v in query_dict.items() if v not in [None, ""]}
        return (search_filters, [key for key in query_dict])


class ResultDataset(BaseDataset):
    @BaseDataset.ModalitiesInStudy.setter
    def ModalitiesInStudy(self, value: str | list[str]) -> None:
        self._ds.ModalitiesInStudy = value

    def __contains__(self, keyword: str) -> bool:
        return keyword in self._ds


def _set_dataset_value(ds: Dataset, k: str, v: Any) -> None:
    t = datadict.tag_for_keyword(k)
    if t is None:
        raise ValueError(f"Unknown DICOM tag with keyword: {k}")

    vr = datadict.dictionary_VR(t)

    try:
        if v is None:
            setattr(ds, k, "")
        elif vr == "DA":
            date = convert_to_dicom_date(v)
            setattr(ds, k, date)
        elif vr == "TM":
            time = convert_to_dicom_time(v)
            setattr(ds, k, time)
        elif vr == "DT":
            datetime = convert_to_dicom_datetime(v)
            setattr(ds, k, datetime)
        else:
            elem = DataElement(t, vr, v)
            ds.add(elem)
    except ValueError as err:
        raise ValueError(f"Invalid value for DICOM tag '{k}' (VR {vr}): {v} ({str(err)})") from err
