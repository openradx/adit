from io import BytesIO

import pandas as pd
import pytest

from adit.batch_transfer.parsers import BatchTransferFileParser
from adit.core.errors import (
    BatchFileContentError,
    BatchFileFormatError,
    BatchFileSizeError,
)


@pytest.fixture
def data():
    return pd.DataFrame(
        [
            ["111", "1.2.3", "1.2.3.1", "pseudo1"],
            ["222", "1.2.4", "1.2.4.1", "pseudo2"],
            ["222", "1.2.4", "1.2.4.2", "pseudo2"],
        ],
        columns=["PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Pseudonym"],
    )


@pytest.fixture(scope="session")
def create_batch_file():
    def _create_batch_file(df: pd.DataFrame):
        batch_file = BytesIO()
        df.to_excel(batch_file, index=False, engine="openpyxl")
        return batch_file

    return _create_batch_file


def test_same_studies_are_grouped_together(create_batch_file, data):
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    tasks = parser.parse(file, 100)

    assert len(tasks) == 2

    assert tasks[0].patient_id == data["PatientID"][0]
    assert tasks[0].study_uid == data["StudyInstanceUID"][0]
    assert tasks[0].series_uids == [data["SeriesInstanceUID"][0]]

    assert tasks[1].patient_id == data["PatientID"][1]
    assert tasks[1].study_uid == data["StudyInstanceUID"][1]
    assert tasks[1].series_uids == [data["SeriesInstanceUID"][1], data["SeriesInstanceUID"][2]]


def test_can_parse_without_series_uid(create_batch_file, data):
    data.drop(columns=["SeriesInstanceUID"], inplace=True)
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    tasks = parser.parse(file, 100)

    assert len(tasks) == 2
    assert tasks[0].series_uids == []


def test_can_not_transfer_unpseudonymized_without_permission(create_batch_file, data):
    data.loc[0, "Pseudonym"] = ""
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=False)

    with pytest.raises(BatchFileContentError):
        parser.parse(file, 100)


def test_consistent_rows_pass(create_batch_file, data):
    # The default fixture data is internally consistent (the repeated study/
    # patient rows agree on patient_id and pseudonym), so it must validate.
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    tasks = parser.parse(file, 100)

    assert len(tasks) == 2


def test_same_study_uid_with_different_patient_id_raises(create_batch_file):
    # Two rows share StudyInstanceUID 1.2.3 but map it to different PatientIDs.
    df = pd.DataFrame(
        [
            ["111", "1.2.3", "1.2.3.1", "pseudo1"],
            ["222", "1.2.3", "1.2.3.2", "pseudo1"],
        ],
        columns=["PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Pseudonym"],
    )
    file = create_batch_file(df)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    with pytest.raises(BatchFileContentError) as exc_info:
        parser.parse(file, 100)

    assert "can't belong to different Patient IDs" in str(exc_info.value)


def test_same_patient_id_with_different_pseudonym_raises(create_batch_file):
    # Two rows share PatientID 111 but assign it conflicting pseudonyms.
    df = pd.DataFrame(
        [
            ["111", "1.2.3", "1.2.3.1", "pseudo1"],
            ["111", "1.2.4", "1.2.4.1", "pseudo2"],
        ],
        columns=["PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Pseudonym"],
    )
    file = create_batch_file(df)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    with pytest.raises(BatchFileContentError) as exc_info:
        parser.parse(file, 100)

    assert "can't have different pseudonyms" in str(exc_info.value)


def test_unpseudonymized_batch_passes_cross_row_validation(create_batch_file):
    # No Pseudonym column at all (an unpseudonymized transfer). The cross-row
    # validation must not raise KeyError on the absent pseudonym field.
    df = pd.DataFrame(
        [
            ["111", "1.2.3", "1.2.3.1"],
            ["222", "1.2.4", "1.2.4.1"],
        ],
        columns=["PatientID", "StudyInstanceUID", "SeriesInstanceUID"],
    )
    file = create_batch_file(df)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    tasks = parser.parse(file, 100)

    assert len(tasks) == 2


def test_invalid_file_raises_format_error():
    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    not_a_spreadsheet = BytesIO(b"definitely not an xlsx file")

    with pytest.raises(BatchFileFormatError):
        parser.parse(not_a_spreadsheet, 100)


def test_exceeding_max_batch_size_raises(create_batch_file, data):
    # The fixture has three rows; capping the batch below that must raise.
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    with pytest.raises(BatchFileSizeError):
        parser.parse(file, 2)
