from datetime import date
from io import BytesIO

import pandas as pd
import pytest

from adit.batch_query.parsers import BatchQueryFileParser
from adit.core.errors import (
    BatchFileContentError,
    BatchFileFormatError,
    BatchFileSizeError,
)
from adit.core.utils.testing_helpers import create_excel_file


@pytest.fixture
def columns():
    return [
        "PatientID",
        "PatientName",
        "PatientBirthDate",
        "AccessionNumber",
        "From",
        "Until",
        "Modality",
        "StudyDescription",
        "SeriesDescription",
        "SeriesNumber",
        "Pseudonym",
    ]


def build_file(df: pd.DataFrame) -> BytesIO:
    """Turn a DataFrame into an in-memory xlsx using the shared helper.

    The helper returns a Playwright FilePayload (a dict with a ``buffer`` of
    bytes); the parser expects a file-like object, so we wrap the bytes.
    """
    payload = create_excel_file(df, "batch_query.xlsx")
    return BytesIO(payload["buffer"])


def parse(df: pd.DataFrame, max_batch_size: int | None = 100):
    parser = BatchQueryFileParser()
    return parser.parse(build_file(df), max_batch_size)


# --- Valid input -----------------------------------------------------------


def test_parses_valid_spreadsheet(columns):
    df = pd.DataFrame(
        [
            ["1001", "", "", "", "2019-06-03", "2019-06-05", "CT, SR", "", "", "", "pseudo1"],
            ["", "Coconut, Coco", "1976-12-09", "", "", "", "MR", "", "", "", ""],
            ["1003", "", "", "0062094311", "", "", "", "", "", "", ""],
        ],
        columns=columns,
    )

    tasks = parse(df)

    assert len(tasks) == 3

    # Row 1: PatientID + date range + comma separated modalities.
    assert tasks[0].patient_id == "1001"
    assert tasks[0].study_date_start == date(2019, 6, 3)
    assert tasks[0].study_date_end == date(2019, 6, 5)
    assert tasks[0].modalities == ["CT", "SR"]
    assert tasks[0].pseudonym == "pseudo1"
    # + 2 because of header row and zero-based index.
    assert tasks[0].lines == [2]

    # Row 2: identified by name + birth date; name normalized to DICOM caret form.
    assert tasks[1].patient_name == "Coconut^Coco"
    assert tasks[1].patient_birth_date == date(1976, 12, 9)
    assert tasks[1].modalities == ["MR"]
    assert tasks[1].lines == [3]

    # Row 3: PatientID + accession number (no modality required then).
    assert tasks[2].patient_id == "1003"
    assert tasks[2].accession_number == "0062094311"
    assert tasks[2].lines == [4]


def test_series_numbers_are_split_on_comma(columns):
    df = pd.DataFrame(
        [["1001", "", "", "", "", "", "CT", "", "", "1, 2 , 3", ""]],
        columns=columns,
    )

    tasks = parse(df)

    assert tasks[0].series_numbers == ["1", "2", "3"]


def test_empty_date_columns_become_none(columns):
    df = pd.DataFrame(
        [["1001", "", "", "", "", "", "CT", "", "", "", ""]],
        columns=columns,
    )

    tasks = parse(df)

    assert tasks[0].study_date_start is None
    assert tasks[0].study_date_end is None
    assert tasks[0].patient_birth_date is None


def test_fully_empty_rows_are_skipped(columns):
    df = pd.DataFrame(
        [
            ["1001", "", "", "", "", "", "CT", "", "", "", ""],
            ["", "", "", "", "", "", "", "", "", "", ""],
            ["1002", "", "", "", "", "", "MR", "", "", "", ""],
        ],
        columns=columns,
    )

    tasks = parse(df)

    assert len(tasks) == 2
    assert tasks[0].patient_id == "1001"
    assert tasks[1].patient_id == "1002"
    # Line numbers reflect the original spreadsheet rows (blank row 3 skipped).
    assert tasks[0].lines == [2]
    assert tasks[1].lines == [4]


def test_header_only_file_yields_no_tasks(columns):
    df = pd.DataFrame([], columns=columns)

    tasks = parse(df)

    assert tasks == []


# --- Format / malformed input ---------------------------------------------


def test_non_xlsx_input_raises_format_error():
    parser = BatchQueryFileParser()
    not_a_spreadsheet = BytesIO(b"this is plain text, not a real xlsx file")

    with pytest.raises(BatchFileFormatError):
        parser.parse(not_a_spreadsheet, 100)


def test_truncated_xlsx_input_raises_format_error(columns):
    df = pd.DataFrame(
        [["1001", "", "", "", "", "", "CT", "", "", "", ""]],
        columns=columns,
    )
    payload = create_excel_file(df, "batch_query.xlsx")
    # Corrupt the zip container by keeping only a prefix of the bytes.
    truncated = BytesIO(payload["buffer"][:50])

    parser = BatchQueryFileParser()
    with pytest.raises(BatchFileFormatError):
        parser.parse(truncated, 100)


def test_empty_file_raises_format_error():
    parser = BatchQueryFileParser()
    with pytest.raises(BatchFileFormatError):
        parser.parse(BytesIO(b""), 100)


# --- Missing / wrong columns ----------------------------------------------


def test_wrong_columns_yield_no_tasks():
    # None of the expected columns are present, so the parser recognizes no
    # values: every row counts as empty and is skipped, leaving no tasks. The
    # data in the unknown columns is simply ignored rather than raising.
    df = pd.DataFrame([["foo", "bar"]], columns=["Alpha", "Beta"])

    assert parse(df) == []


def test_missing_modality_column_raises_content_error(columns):
    # PatientID present but no Modality and no AccessionNumber -> clean() fails.
    cols = [c for c in columns if c != "Modality"]
    df = pd.DataFrame([["1001", "", "", "", "", "", "", "", "", ""]], columns=cols)

    with pytest.raises(BatchFileContentError):
        parse(df)


def test_unidentifiable_patient_raises_content_error(columns):
    # Modality present but patient is not identifiable (no PatientID and no
    # PatientName + PatientBirthDate pair) -> clean() fails.
    df = pd.DataFrame(
        [["", "", "", "", "", "", "CT", "", "", "", ""]],
        columns=columns,
    )

    with pytest.raises(BatchFileContentError):
        parse(df)


# --- Bad field values ------------------------------------------------------


def test_garbage_date_raises_content_error(columns):
    df = pd.DataFrame(
        [["1001", "", "not-a-date", "", "", "", "CT", "", "", "", ""]],
        columns=columns,
    )

    with pytest.raises(BatchFileContentError):
        parse(df)


def test_non_letter_modality_raises_content_error(columns):
    # modalities are validated with letters_validator; digits are rejected.
    df = pd.DataFrame(
        [["1001", "", "", "", "", "", "123", "", "", "", ""]],
        columns=columns,
    )

    with pytest.raises(BatchFileContentError):
        parse(df)


# --- Row count constraint --------------------------------------------------


def test_exceeding_max_batch_size_raises_size_error(columns):
    rows = [
        [str(1000 + i), "", "", "", "", "", "CT", "", "", "", ""] for i in range(3)
    ]
    df = pd.DataFrame(rows, columns=columns)

    with pytest.raises(BatchFileSizeError):
        parse(df, max_batch_size=2)


def test_at_max_batch_size_is_allowed(columns):
    rows = [
        [str(1000 + i), "", "", "", "", "", "CT", "", "", "", ""] for i in range(2)
    ]
    df = pd.DataFrame(rows, columns=columns)

    tasks = parse(df, max_batch_size=2)

    assert len(tasks) == 2


def test_no_max_batch_size_allows_any_number(columns):
    rows = [
        [str(1000 + i), "", "", "", "", "", "CT", "", "", "", ""] for i in range(5)
    ]
    df = pd.DataFrame(rows, columns=columns)

    tasks = parse(df, max_batch_size=None)

    assert len(tasks) == 5
