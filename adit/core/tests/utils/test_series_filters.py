from dataclasses import dataclass, field
from datetime import date, datetime
from typing import cast

import pytest
from pydicom import Dataset

from adit.core.utils.dicom_dataset import ResultDataset
from adit.core.utils.series_filters import (
    DiscoveredSeries,
    FilterSpec,
    parse_filters,
    select_study_series,
    study_matches_filter,
)


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


def test_series_only_filter_does_not_read_study_fields():
    study = cast(ResultDataset, _StudyWithoutKeys())
    mf = FilterSpec(series_description="Ax*")

    assert study_matches_filter(mf, study, _no_institution_lookup)


def test_institution_filter_not_applied_on_study_does_not_read_study_fields():
    study = cast(ResultDataset, _StudyWithoutKeys())
    mf = FilterSpec(institution_name="Uni*", apply_institution_on_study=False)

    assert study_matches_filter(mf, study, _no_institution_lookup)


def test_institution_lookup_returning_true_matches():
    mf = FilterSpec(institution_name="Uni*")

    assert study_matches_filter(mf, _study(), lambda pattern: True)


def test_age_bounds_are_inclusive():
    study = _study(birth_date="19990615", study_date="20240601")  # 24 on the study date

    assert study_matches_filter(FilterSpec(min_age=24, max_age=24), study, _no_institution_lookup)


def test_study_matches_filter_rejects_exclude_mode():
    mf = FilterSpec(mode="exclude", modality="CT")

    with pytest.raises(AssertionError):
        study_matches_filter(mf, _study(), _no_institution_lookup)


@dataclass(frozen=True)
class _Facts:
    ModalitiesInStudy: list[str] = field(default_factory=lambda: ["CT", "SR"])
    StudyDescription: str = "CT Kopf nativ"
    PatientBirthDate: date | None = date(1999, 6, 1)
    StudyDate: date | None = date(2024, 6, 1)


def _series(
    uid: str,
    modality: str = "CT",
    description: str = "Axial",
    institution: str = "Radiology",
    birth_date: date | None = date(1999, 6, 1),
) -> DiscoveredSeries:
    return DiscoveredSeries(
        patient_id="PAT1",
        accession_number="",
        study_instance_uid="1.2.3",
        series_instance_uid=uid,
        modality=modality,
        study_description="CT Kopf nativ",
        series_description=description,
        series_number=1,
        study_datetime=datetime(2024, 6, 1, 12, 0),
        institution_name=institution,
        number_of_images=10,
        patient_birth_date=birth_date,
    )


def _uids(selected: list[DiscoveredSeries]) -> set[str]:
    return {s.series_instance_uid for s in selected}


def test_filter_without_series_conditions_selects_the_whole_study():
    series = [_series("1"), _series("2", modality="SR", description="Dose report")]

    selected = select_study_series(_Facts(), series, [FilterSpec(study_description="CT*")])

    assert _uids(selected) == {"1", "2"}


def test_modality_selects_series_not_studies():
    series = [_series("1"), _series("2", modality="SR")]

    assert _uids(select_study_series(_Facts(), series, [FilterSpec(modality="CT")])) == {"1"}


def test_structured_reports_are_sent_when_a_filter_selects_them():
    series = [_series("1"), _series("2", modality="SR")]
    filters = [FilterSpec(modality="CT"), FilterSpec(modality="SR")]

    assert _uids(select_study_series(_Facts(), series, filters)) == {"1", "2"}


def test_institution_on_study_admits_every_series():
    series = [_series("1", institution="Radiology"), _series("2", institution="External")]

    selected = select_study_series(_Facts(), series, [FilterSpec(institution_name="Radio*")])

    assert _uids(selected) == {"1", "2"}


def test_institution_on_series_selects_matching_series():
    series = [_series("1", institution="Radiology"), _series("2", institution="External")]
    mf = FilterSpec(institution_name="Radio*", apply_institution_on_study=False)

    assert _uids(select_study_series(_Facts(), series, [mf])) == {"1"}


def test_unknown_birth_date_fails_an_age_bounded_include():
    facts = _Facts(PatientBirthDate=None)

    selected = select_study_series(
        facts, [_series("1", birth_date=None)], [FilterSpec(min_age=20, max_age=30)]
    )

    assert selected == []


def test_age_bounded_exclude_drops_series_with_unknown_birth_date():
    facts = _Facts(PatientBirthDate=None)
    filters = [FilterSpec(), FilterSpec(mode="exclude", max_age=18)]

    assert select_study_series(facts, [_series("1", birth_date=None)], filters) == []


def test_exclude_filters_match_case_insensitively():
    series = [_series("1", description="Axial"), _series("2", description="CORONAL")]
    filters = [FilterSpec(modality="CT"), FilterSpec(mode="exclude", series_description="cor*")]

    assert _uids(select_study_series(_Facts(), series, filters)) == {"1"}


def test_study_failing_the_study_conditions_selects_nothing():
    selected = select_study_series(_Facts(), [_series("1")], [FilterSpec(study_description="MR*")])

    assert selected == []


@pytest.mark.parametrize("data", [None, {}, [], "CT"])
def test_parse_filters_needs_a_non_empty_list(data):
    with pytest.raises(ValueError, match="non-empty JSON array"):
        parse_filters(data)


def test_parse_filters_needs_objects():
    with pytest.raises(ValueError, match="Filter #2 must be a JSON object"):
        parse_filters([{"modality": "CT"}, "MR"])


def test_parse_filters_reports_invalid_fields():
    with pytest.raises(ValueError, match="Filter #1: "):
        parse_filters([{"modality": "CT", "unknown": 1}])


def test_parse_filters_needs_an_include_filter():
    with pytest.raises(ValueError, match="mode=include"):
        parse_filters([{"mode": "exclude", "modality": "SR"}])


def test_parse_filters_normalizes_valid_filters():
    [parsed] = parse_filters([{"modality": "CT"}])

    assert parsed["mode"] == "include"
    assert parsed["modality"] == "CT"
