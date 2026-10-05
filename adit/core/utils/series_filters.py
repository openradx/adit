"""Filters that select the series of a study."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, model_validator

from ..errors import DicomError
from .dicom_dataset import ResultDataset
from .dicom_utils import convert_to_python_regex


class FilterSchema(BaseModel):
    """Pydantic model for validating filter JSON objects."""

    mode: Literal["include", "exclude"] = "include"
    modality: str = ""
    institution_name: str = ""
    apply_institution_on_study: bool = True
    study_description: str = ""
    series_description: str = ""
    series_number: int | None = None
    min_age: Annotated[int, "non-negative"] | None = None
    max_age: Annotated[int, "non-negative"] | None = None
    min_number_of_series_related_instances: int | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def check_age_range(self):
        if self.min_age is not None and self.min_age < 0:
            raise ValueError("min_age must be non-negative")
        if self.max_age is not None and self.max_age < 0:
            raise ValueError("max_age must be non-negative")
        if (
            self.min_number_of_series_related_instances is not None
            and self.min_number_of_series_related_instances < 1
        ):
            raise ValueError("min_number_of_series_related_instances must be >= 1")
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError(f"min_age ({self.min_age}) cannot exceed max_age ({self.max_age})")
        return self

    @model_validator(mode="after")
    def check_exclude_has_criteria(self):
        if self.mode != "exclude":
            return self
        has_criterion = bool(
            self.modality
            or self.institution_name
            or self.study_description
            or self.series_description
            or self.series_number is not None
            or self.min_age is not None
            or self.max_age is not None
            or self.min_number_of_series_related_instances is not None
        )
        if not has_criterion:
            raise ValueError("exclude filter must specify at least one criterion")
        return self


@dataclass(frozen=True)
class FilterSpec:
    """Unified filter representation.

    Built from one entry of a filters_json list.
    """

    mode: Literal["include", "exclude"] = "include"
    modality: str = ""
    institution_name: str = ""
    apply_institution_on_study: bool = True
    study_description: str = ""
    series_description: str = ""
    series_number: int | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_number_of_series_related_instances: int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "FilterSpec":
        mode = d.get("mode", "include")
        if mode not in ("include", "exclude"):
            raise DicomError(f"Invalid filter mode: {mode!r}")
        return cls(
            mode=mode,
            modality=d.get("modality", ""),
            institution_name=d.get("institution_name", ""),
            apply_institution_on_study=d.get("apply_institution_on_study", True),
            study_description=d.get("study_description", ""),
            series_description=d.get("series_description", ""),
            series_number=d.get("series_number"),
            min_age=d.get("min_age"),
            max_age=d.get("max_age"),
            min_number_of_series_related_instances=d.get("min_number_of_series_related_instances"),
        )


@dataclass(frozen=True)
class DiscoveredSeries:
    patient_id: str
    accession_number: str
    study_instance_uid: str
    series_instance_uid: str
    modality: str
    study_description: str
    series_description: str
    series_number: int | None
    study_datetime: datetime
    institution_name: str
    number_of_images: int
    patient_birth_date: date | None = None


def dicom_match(pattern: str, value: str | None, case_insensitive: bool = False) -> bool:
    # Callers only pass non-PN fields (institution_name, study_description,
    # series_description). Include filters compare case-sensitively to stay
    # consistent with PACS-side matching of non-PN fields; exclude filters are
    # applied client-side only and pass case_insensitive=True.
    if not pattern:
        return True
    if value is None:
        return False
    regex = convert_to_python_regex(pattern, case_insensitive=case_insensitive)
    return bool(regex.fullmatch(str(value)))


def age_at_study(birth_date: date, study_date: date) -> int:
    """Return the patient's age in whole years on the study date."""
    age = study_date.year - birth_date.year
    if (study_date.month, study_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def study_matches_filter(
    mf: FilterSpec, study: ResultDataset, has_institution: Callable[[str], bool]
) -> bool:
    """Test whether *study* can hold series selected by the include filter *mf*.

    Only checks what is known on study level; the series are tested afterwards with
    series_matches_filter. Study fields are read only when the filter uses them.

    *has_institution* receives the filter's institution pattern (DICOM wildcards) and
    answers whether any series of the study has an InstitutionName matching it,
    case-sensitively as dicom_match does. It is only called when the filter asks for an
    institution on study level and the earlier checks passed, so callers can look the
    institutions up lazily.
    """
    assert mf.mode == "include"
    if mf.modality and mf.modality not in study.ModalitiesInStudy:
        return False

    if mf.study_description and not dicom_match(mf.study_description, study.StudyDescription):
        return False

    if mf.institution_name and mf.apply_institution_on_study:
        if not has_institution(mf.institution_name):
            return False

    # An unknown birth date passes here; series_matches_filter decides about it.
    if mf.min_age is not None or mf.max_age is not None:
        birth_date = study.PatientBirthDate
        if birth_date and study.StudyDate:
            age = age_at_study(birth_date, study.StudyDate)
            if mf.min_age is not None and age < mf.min_age:
                return False
            if mf.max_age is not None and age > mf.max_age:
                return False

    return True


def series_matches_filter(
    series: DiscoveredSeries,
    mf: FilterSpec,
    check_institution: bool = True,
    age_permissive: bool = False,
) -> bool:
    """Test whether *series* satisfies all non-empty criteria on *mf*.

    ``check_institution=False`` skips the institution check — the include
    path uses this when ``apply_institution_on_study`` has already resolved
    the check at study level.  ``age_permissive=True`` treats an unknown
    ``patient_birth_date`` as passing the age check; excludes set this so
    a series with an unverifiable age is dropped by an age-bounded exclude
    filter.  The strict default is used by include filters so that an
    unknown age also fails inclusion — in both directions, a series whose
    age can't be determined is dropped.

    String criteria on include filters are matched case-sensitively, in line
    with PACS-side matching of non-PN fields.  Exclude filters are applied
    client-side only (they never reach the PACS), so they match
    case-insensitively — scanner naming conventions vary in capitalization
    (COR/Cor/cor) and an exclude should catch all variants.
    """
    case_insensitive = mf.mode == "exclude"
    if mf.modality and mf.modality != series.modality:
        return False
    if check_institution and mf.institution_name:
        if not dicom_match(mf.institution_name, series.institution_name, case_insensitive):
            return False
    if mf.study_description and not dicom_match(
        mf.study_description, series.study_description, case_insensitive
    ):
        return False
    if mf.series_description and not dicom_match(
        mf.series_description, series.series_description, case_insensitive
    ):
        return False
    if mf.series_number is not None:
        if series.series_number is None or mf.series_number != series.series_number:
            return False
    if mf.min_age is not None or mf.max_age is not None:
        if series.patient_birth_date:
            age = age_at_study(series.patient_birth_date, series.study_datetime.date())
            if mf.min_age is not None and age < mf.min_age:
                return False
            if mf.max_age is not None and age > mf.max_age:
                return False
        elif not age_permissive:
            return False
    if mf.min_number_of_series_related_instances is not None:
        if series.number_of_images < mf.min_number_of_series_related_instances:
            return False
    return True
