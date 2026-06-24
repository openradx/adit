from datetime import date, datetime, time
from pathlib import Path

import pytest
from django.test import override_settings
from pydicom import Dataset

from adit.core.utils.dicom_utils import (
    construct_download_file_path,
    convert_to_dicom_date,
    convert_to_dicom_datetime,
    convert_to_dicom_time,
    convert_to_python_date,
    convert_to_python_regex,
    convert_to_python_time,
    has_wildcards,
    person_name_to_dicom,
)


def test_convert_to_dicom_date():
    # Test with single dates
    assert convert_to_dicom_date("20230831") == "20230831"
    assert convert_to_dicom_date(date(2023, 8, 31)) == "20230831"

    # Test with date ranges
    assert convert_to_dicom_date("20220309 - 20230831") == "20220309-20230831"
    assert convert_to_dicom_date((date(2022, 3, 9), date(2023, 8, 31))) == "20220309-20230831"


def test_convert_to_dicom_time():
    # Test with single times
    assert convert_to_dicom_time("080000") == "080000"
    assert convert_to_dicom_time(time(8, 0, 0)) == "080000"

    # Test with time ranges
    assert convert_to_dicom_time("080000 - 230000") == "080000-230000"
    assert convert_to_dicom_time((time(8, 0, 0), time(23, 0, 0))) == "080000-230000"


def test_convert_to_dicom_datetime():
    # Test with single datetime
    assert convert_to_dicom_datetime("20220309080000") == "20220309080000"
    assert convert_to_dicom_datetime(datetime(2022, 3, 9, 8, 0, 0)) == "20220309080000"

    # Test with datetime range
    assert (
        convert_to_dicom_datetime("20220309080000-20230831230000")
        == "20220309080000-20230831230000"
    )
    assert (
        convert_to_dicom_datetime((datetime(2022, 3, 9, 8, 0, 0), datetime(2023, 8, 31, 23, 0, 0)))
        == "20220309080000-20230831230000"
    )


def test_convert_to_python_date():
    assert convert_to_python_date("20230831") == date(2023, 8, 31)


def test_convert_to_python_time():
    assert convert_to_python_time("080000") == time(8, 0, 0)


def test_convert_to_python_regex_exact_match():
    # No wildcard = exact whole-value match (DICOM Single Value Matching)
    pattern = convert_to_python_regex("query")
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("QUERY") is None  # case-sensitive by default
    assert pattern.fullmatch("queryX") is None
    assert pattern.fullmatch("Xquery") is None
    assert pattern.fullmatch("XqueryX") is None


def test_convert_to_python_regex_starts_with():
    # Trailing * = prefix match
    pattern = convert_to_python_regex("query*")
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("queryX") is not None
    assert pattern.fullmatch("Xquery") is None
    assert pattern.fullmatch("XqueryX") is None


def test_convert_to_python_regex_ends_with():
    # Leading * = suffix match
    pattern = convert_to_python_regex("*query")
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("Xquery") is not None
    assert pattern.fullmatch("queryX") is None
    assert pattern.fullmatch("XqueryX") is None


def test_convert_to_python_regex_contains():
    # Surrounding * = substring match
    pattern = convert_to_python_regex("*query*")
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("queryX") is not None
    assert pattern.fullmatch("Xquery") is not None
    assert pattern.fullmatch("XqueryX") is not None
    assert pattern.fullmatch("unrelated") is None


def test_convert_to_python_regex_single_char_wildcard():
    # ? matches exactly one character (DICOM wildcard)
    pattern = convert_to_python_regex("qu?ry")
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("qu3ry") is not None
    assert pattern.fullmatch("quary") is not None
    assert pattern.fullmatch("qury") is None  # missing char
    assert pattern.fullmatch("queery") is None  # too many chars
    assert pattern.fullmatch("XqueryX") is None  # not anchored


def test_convert_to_python_regex_case_sensitive_by_default():
    pattern = convert_to_python_regex("query")
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("QUERY") is None
    assert pattern.fullmatch("Query") is None


def test_convert_to_python_regex_case_insensitive():
    pattern = convert_to_python_regex("query", case_insensitive=True)
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("QUERY") is not None
    assert pattern.fullmatch("Query") is not None


def test_convert_to_python_regex_escapes_regex_metacharacters():
    # Regex metachars in the input must be treated as literals, not regex syntax
    pattern = convert_to_python_regex("a.b")
    assert pattern.fullmatch("a.b") is not None
    assert pattern.fullmatch("aXb") is None  # `.` must NOT match arbitrary char


# --- error branches of the DICOM date/time/datetime converters --------------


def test_convert_to_dicom_date_invalid_raises():
    with pytest.raises(ValueError, match="Invalid date format"):
        convert_to_dicom_date("not-a-date")


def test_convert_to_dicom_time_invalid_raises():
    with pytest.raises(ValueError, match="Invalid time format"):
        convert_to_dicom_time("99:99")


def test_convert_to_dicom_datetime_invalid_raises():
    with pytest.raises(ValueError, match="Invalid datetime format"):
        convert_to_dicom_datetime("not-a-datetime")


def test_convert_to_dicom_date_range_with_too_many_parts_raises():
    # Three dash-separated parts is not a valid 2-element range.
    with pytest.raises(ValueError, match="Invalid date format"):
        convert_to_dicom_date("20220101-20220202-20220303")


# --- has_wildcards ----------------------------------------------------------


@pytest.mark.parametrize("value", ["a*b", "a?b", "*", "?", "PAT*"])
def test_has_wildcards_true(value):
    assert has_wildcards(value) is True


@pytest.mark.parametrize("value", ["abc", "1.2.3", ""])
def test_has_wildcards_false(value):
    assert has_wildcards(value) is False


# --- person_name_to_dicom ---------------------------------------------------


def test_person_name_to_dicom_replaces_comma_with_caret():
    assert person_name_to_dicom("Doe, John") == "Doe^John"


def test_person_name_to_dicom_without_comma_unchanged():
    assert person_name_to_dicom("Doe") == "Doe"


def test_person_name_to_dicom_with_wildcards():
    assert person_name_to_dicom("Doe, John", add_wildcards=True) == "Doe*^John*"


# --- construct_download_file_path -------------------------------------------


def _instance(**attrs) -> Dataset:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.SeriesInstanceUID = "1.2.3.4"
    for key, value in attrs.items():
        setattr(ds, key, value)
    return ds


STUDY_DATE = date(2023, 8, 31)
STUDY_TIME = time(8, 0, 0)


@override_settings(CREATE_SERIES_SUB_FOLDERS=True, EXCLUDE_MODALITIES=[])
def test_download_path_with_series_subfolder_and_series_number():
    ds = _instance(SeriesNumber="3", SeriesDescription="Localizer")
    base = Path("/tmp/downloads")
    path = construct_download_file_path(ds, base, "PAT001", STUDY_DATE, STUDY_TIME, ["CT"])

    assert str(path).startswith(str(base))
    # Patient folder uses the patient id (no pseudonym).
    assert "PAT001" in str(path)
    # Study folder prefix is date-time-modalities.
    assert "20230831-080000-CT" in str(path)
    # Series subfolder is "<series_number>-<series_description>".
    assert "3-Localizer" in str(path)
    assert path.name == "1.2.3.4.5.dcm"


@override_settings(CREATE_SERIES_SUB_FOLDERS=True, EXCLUDE_MODALITIES=[])
def test_download_path_without_series_number_uses_series_uid():
    ds = _instance()  # no SeriesNumber
    base = Path("/tmp/downloads")
    path = construct_download_file_path(ds, base, "PAT001", STUDY_DATE, STUDY_TIME, ["CT"])

    # With no series number the series folder is the SeriesInstanceUID.
    assert "1.2.3.4" in str(path.parent)


@override_settings(CREATE_SERIES_SUB_FOLDERS=False, EXCLUDE_MODALITIES=[])
def test_download_path_without_series_subfolder():
    ds = _instance(SeriesNumber="3")
    base = Path("/tmp/downloads")
    path = construct_download_file_path(ds, base, "PAT001", STUDY_DATE, STUDY_TIME, ["CT"])

    # The file sits directly in the study folder; no series subfolder.
    assert path.parent.name == "20230831-080000-CT"


@override_settings(CREATE_SERIES_SUB_FOLDERS=False, EXCLUDE_MODALITIES=["PR", "SR"])
def test_download_path_uses_pseudonym_and_excludes_modalities():
    ds = _instance()
    base = Path("/tmp/downloads")
    path = construct_download_file_path(
        ds,
        base,
        "PAT001",
        STUDY_DATE,
        STUDY_TIME,
        ["CT", "SR"],
        pseudonym="PSEUDO1",
    )

    # The pseudonym replaces the patient id in the base folder.
    assert "PSEUDO1" in str(path)
    assert "PAT001" not in str(path)
    # SR is excluded when a pseudonym is given; only CT remains.
    assert "20230831-080000-CT" in str(path)
    assert "SR" not in path.parent.name


@override_settings(CREATE_SERIES_SUB_FOLDERS=False, EXCLUDE_MODALITIES=[])
def test_download_path_unknown_modalities_when_empty():
    ds = _instance()
    base = Path("/tmp/downloads")
    path = construct_download_file_path(ds, base, "PAT001", STUDY_DATE, STUDY_TIME, [])

    # No modalities -> "UNKNOWN" placeholder in the study folder name.
    assert "UNKNOWN" in str(path)


@override_settings(CREATE_SERIES_SUB_FOLDERS=True, EXCLUDE_MODALITIES=[])
def test_download_path_sanitizes_path_traversal_in_pseudonym():
    """A pseudonym attempting path traversal must be sanitized, keeping the file
    inside the base folder (the security guard in construct_download_file_path)."""
    ds = _instance(SeriesNumber="1", SeriesDescription="Series")
    base = Path("/tmp/downloads")
    # Slashes/dots are sanitized to underscores, so this cannot escape the base.
    path = construct_download_file_path(
        ds,
        base,
        "PAT001",
        STUDY_DATE,
        STUDY_TIME,
        ["CT"],
        pseudonym="../../etc/passwd",
    )

    resolved_base = base.resolve()
    assert path.resolve().is_relative_to(resolved_base)
    # The traversal sequence must not survive as real parent-directory components.
    assert ".." not in path.relative_to(base).parts


@override_settings(CREATE_SERIES_SUB_FOLDERS=True, EXCLUDE_MODALITIES=[])
def test_download_path_dot_pseudonym_falls_back_to_safe_default():
    """A pseudonym that sanitizes to '.' or '..' is replaced by a safe default
    (construct_download_file_path._safe_path_component)."""
    ds = _instance(SeriesNumber="1")
    base = Path("/tmp/downloads")
    # "." stays "." after sanitize_filename (it only strips/maps special chars),
    # which the guard maps to "safe_default".
    path = construct_download_file_path(
        ds, base, "PAT001", STUDY_DATE, STUDY_TIME, ["CT"], pseudonym="."
    )

    assert "safe_default" in str(path)
    assert path.resolve().is_relative_to(base.resolve())
