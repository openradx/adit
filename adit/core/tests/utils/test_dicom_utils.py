from datetime import date, datetime, time

from ...utils.dicom_utils import (
    convert_to_dicom_date,
    convert_to_dicom_datetime,
    convert_to_dicom_time,
    convert_to_python_date,
    convert_to_python_time,
)


def test_convert_to_dicom_date():
    # Test with single dates
    assert convert_to_dicom_date("20230831") == "20230831"
    assert convert_to_dicom_date(date(2023, 8, 31)) == "20230831"

    # Test with date ranges
    assert convert_to_dicom_date("20220309 - 20230831") == "20220309 - 20230831"
    assert convert_to_dicom_date((date(2022, 3, 9), date(2023, 8, 31))) == "20220309 - 20230831"


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
