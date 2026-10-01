from typing import cast

from pydicom import Dataset

from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.filters import FilterSpec, study_matches_filter


def _study(**values) -> ResultDataset:
    ds = Dataset()
    ds.ModalitiesInStudy = values.get("modalities", ["CT"])
    ds.StudyDescription = values.get("description", "CT Kopf nativ")
    ds.StudyDate = values.get("study_date", "20240601")
    if "birth_date" in values:
        ds.PatientBirthDate = values["birth_date"]
    return ResultDataset(ds)


def _no_institution_lookup(name: str) -> bool:
    raise AssertionError("the institution must not be looked up here")


def test_study_without_the_filtered_modality_does_not_match():
    assert not study_matches_filter(FilterSpec(modality="MR"), _study(), _no_institution_lookup)


def test_study_description_must_match():
    mf = FilterSpec(study_description="CT*")

    assert study_matches_filter(mf, _study(), _no_institution_lookup)
    assert not study_matches_filter(mf, _study(description="MR Knie"), _no_institution_lookup)


class _StudyWithoutKeys:
    """Raises like ResultDataset does when a PACS omits these keys."""

    @property
    def ModalitiesInStudy(self):
        raise AttributeError("ModalitiesInStudy")

    @property
    def StudyDescription(self):
        raise AttributeError("StudyDescription")


def test_study_fields_are_only_read_when_the_filter_uses_them():
    study = cast(ResultDataset, _StudyWithoutKeys())

    assert study_matches_filter(FilterSpec(), study, _no_institution_lookup)


def test_institution_is_only_looked_up_when_filtered_on_study_level():
    looked_up: list[str] = []

    def lookup(name: str) -> bool:
        looked_up.append(name)
        return False

    assert not study_matches_filter(FilterSpec(institution_name="Uni*"), _study(), lookup)
    assert looked_up == ["Uni*"]

    looked_up.clear()
    mf = FilterSpec(institution_name="Uni*", apply_institution_on_study=False)
    assert study_matches_filter(mf, _study(), lookup)
    assert looked_up == []


def test_institution_is_not_looked_up_when_an_earlier_check_fails():
    mf = FilterSpec(modality="MR", institution_name="Uni*")

    assert not study_matches_filter(mf, _study(), _no_institution_lookup)


def test_age_bounds_use_birth_date_and_study_date():
    study = _study(birth_date="19990615", study_date="20240601")  # 24 on the study date

    assert study_matches_filter(FilterSpec(min_age=20, max_age=30), study, _no_institution_lookup)
    assert not study_matches_filter(FilterSpec(min_age=25), study, _no_institution_lookup)
    assert not study_matches_filter(FilterSpec(max_age=23), study, _no_institution_lookup)


def test_unknown_birth_date_is_left_to_the_series_check():
    assert study_matches_filter(FilterSpec(min_age=20), _study(), _no_institution_lookup)
