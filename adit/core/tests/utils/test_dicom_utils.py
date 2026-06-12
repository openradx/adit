from datetime import date, datetime, time

from adit.core.utils.dicom_utils import (
    convert_to_dicom_date,
    convert_to_dicom_datetime,
    convert_to_dicom_time,
    convert_to_python_date,
    convert_to_python_regex,
    convert_to_python_time,
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
    assert pattern.fullmatch("QUERY") is not None  # case-insensitive by default
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


def test_convert_to_python_regex_case_sensitive():
    pattern = convert_to_python_regex("query", case_sensitive=True)
    assert pattern.fullmatch("query") is not None
    assert pattern.fullmatch("QUERY") is None
    assert pattern.fullmatch("Query") is None


def test_convert_to_python_regex_escapes_regex_metacharacters():
    # Regex metachars in the input must be treated as literals, not regex syntax
    pattern = convert_to_python_regex("a.b")
    assert pattern.fullmatch("a.b") is not None
    assert pattern.fullmatch("aXb") is None  # `.` must NOT match arbitrary char
