from io import BytesIO

import pandas as pd
import pytest

from adit.core.errors import BatchFileContentError

from ..parsers import BatchTransferFileParser


@pytest.fixture
def data():
    return pd.DataFrame(
        [
            ["111", "1.2.3", "1.2.3.1", "pseudo1"],
            ["222", "1.2.4", "1.2.4.1", "pseudo2"],
            ["222", "1.2.4", "1.2.4.2", "pseudo2"],
        ],
        columns=["PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Pseudonym"],  # type: ignore
    )


@pytest.fixture(scope="session")
def create_batch_file():
    def _create_batch_file(df: pd.DataFrame):
        batch_file = BytesIO()
        df.to_excel(batch_file, index=False, engine="openpyxl")  # type: ignore
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
    data["Pseudonym"][0] = ""
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=False)

    with pytest.raises(BatchFileContentError):
        parser.parse(file, 100)


# TODO: test with invalid file

# TODO: test same patient_id only has one pseudonym

# TODO: same study_uid belongt to only one patient_id

# TODO: test max batch size
