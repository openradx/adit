from io import StringIO

import pytest

from adit.core.errors import BatchFileFormatError

from ..parsers import BatchTransferFileParser


@pytest.fixture
def data():
    return [
        ["PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Pseudonym"],
        ["111", "1.2.3", "1.2.3.1", "pseudo1"],
        ["222", "1.2.4", "1.2.4.1", "pseudo2"],
        ["222", "1.2.4", "1.2.4.2", "pseudo2"],
    ]


@pytest.fixture(scope="session")
def create_batch_file():
    def _create_batch_file(csv_data):
        csv_str = ""
        for row in csv_data:
            csv_str += ";".join(row) + "\n"
        return StringIO(csv_str)

    return _create_batch_file


def test_same_studies_are_grouped_together(create_batch_file, data):
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    tasks = parser.parse(file, 100)

    assert len(tasks) == 2

    assert tasks[0].task_id == 1
    assert tasks[0].patient_id == data[1][0]
    assert tasks[0].study_uid == data[1][1]
    assert tasks[0].series_uids == [data[1][2]]

    assert tasks[1].task_id == 2
    assert tasks[1].patient_id == data[2][0]
    assert tasks[1].study_uid == data[2][1]
    assert sorted(tasks[1].series_uids) == sorted([data[2][2], data[3][2]])


def test_can_parse_without_series_uid(create_batch_file, data):
    for row in data:
        row.pop(2)
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=True)
    tasks = parser.parse(file, 100)

    assert len(tasks) == 2

    assert tasks[0].series_uids is None


def test_can_not_transfer_unpseudonymized_without_permission(create_batch_file, data):
    data[1][3] = ""
    file = create_batch_file(data)

    parser = BatchTransferFileParser(can_transfer_unpseudonymized=False)

    with pytest.raises(BatchFileFormatError):
        parser.parse(file, 100)


# TODO: test same patient_id only has one pseudonym

# TODO: same study_uid belongt to only one patient_id

# TODO: test max batch size
