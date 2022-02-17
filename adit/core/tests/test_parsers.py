from io import StringIO
import pytest
from django.db import models
from ..models import DicomTask
from ..serializers import BatchTaskSerializer
from ..parsers import BatchFileParser
from ..errors import BatchFileFormatError


@pytest.fixture(scope="session")
def create_batch_file():
    def _create_batch_file(csv_data):
        csv_str = ""
        for row in csv_data:
            csv_str += ";".join(row) + "\n"
        return StringIO(csv_str)

    return _create_batch_file


@pytest.fixture
def data():
    return [
        ["TaskID", "PatientName", "StudyInstanceUID", "SeriesInstanceUID"],
        ["1", "Apple, Annie", "1.2.3", "1.2.3.1"],
        ["2", "Coconut, Coco", "1.2.4", "1.2.4.1"],
    ]


@pytest.fixture
def field_to_column_mapping():
    return {
        "task_id": "TaskID",
        "patient_name": "PatientName",
        "study_uid": "StudyInstanceUID",
        "series_uids": "SeriesInstanceUID",
    }


@pytest.fixture(scope="session")
def test_serializer_class():
    class TestTask(DicomTask):  # pylint: disable=too-few-public-methods
        patient_name = models.CharField(max_length=324)
        study_uid = models.CharField(max_length=64)
        series_uids = models.JSONField()

    class TestSerializer(BatchTaskSerializer):
        class Meta(BatchTaskSerializer.Meta):
            model = TestTask
            fields = ["task_id", "patient_name", "study_uid", "series_uids"]

    return TestSerializer


@pytest.fixture
def test_parser(test_serializer_class, field_to_column_mapping):
    class TestParser(BatchFileParser):
        serializer_class = test_serializer_class

    return TestParser(field_to_column_mapping)


def test_valid_data_is_parsed_successfully(create_batch_file, data, test_parser):
    # Arrange
    file = create_batch_file(data)

    # Act
    tasks = test_parser.parse(file, 100)

    # Assert

    # Cave, the parsed tasks may have a different order then the original data

    assert len(tasks) == 2

    task1 = next(task for task in tasks if task.task_id == 1)
    assert task1.patient_name == data[1][1]

    task2 = next(task for task in tasks if task.task_id == 2)
    assert task2.patient_name == data[2][1]


def test_invalid_model_data_raises(create_batch_file, data, test_parser):
    # Arrange
    data[2][1] = ""
    file = create_batch_file(data)

    # Act
    with pytest.raises(BatchFileFormatError) as err:
        test_parser.parse(file, 100)

    # Assert
    assert err.match(r"Invalid data on line 3 \(TaskID 2\)")
    assert err.match(r"PatientName - This field may not be blank")
