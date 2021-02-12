from io import StringIO
import pytest
from django.db import models
from ...models import DicomTask
from ...serializers import BatchTaskSerializer
from ...utils.batch_parsers import BatchFileParser, BatchFileFormatError


@pytest.fixture(scope="session")
def create_csv_file():
    def _create_csv_file(csv_data):
        csv_str = ""
        for row in csv_data:
            csv_str += ";".join(row) + "\n"
        return StringIO(csv_str)

    return _create_csv_file


@pytest.fixture
def data():
    return [
        ["TaskID", "PatientName"],
        ["1", "Apple, Annie"],
        ["2", "Coconut, Coco"],
    ]


@pytest.fixture
def field_to_column_mapping():
    return {
        "task_id": "TaskID",
        "patient_name": "PatientName",
    }


@pytest.fixture(scope="session")
def test_serializer_class():
    class TestTask(DicomTask):  # pylint: disable=too-few-public-methods
        patient_name = models.CharField(max_length=324)

    class TestSerializer(BatchTaskSerializer):
        class Meta(BatchTaskSerializer.Meta):
            model = TestTask
            fields = ["task_id", "patient_name"]

    return TestSerializer


@pytest.fixture
def test_parser(test_serializer_class, field_to_column_mapping):
    class TestParser(BatchFileParser):
        serializer_class = test_serializer_class

    return TestParser(field_to_column_mapping)


def test_valid_data_is_parsed_successfully(create_csv_file, data, test_parser):
    # Arrange
    file = create_csv_file(data)

    # Act
    tasks = test_parser.parse(file, 100)

    # Assert
    assert tasks[0].task_id == int(data[1][0])
    assert tasks[1].task_id == int(data[2][0])
    assert tasks[0].patient_name == data[1][1]
    assert tasks[1].patient_name == data[2][1]


def test_invalid_model_data_raises(create_csv_file, data, test_parser):
    # Arrange
    data[2][1] = ""
    file = create_csv_file(data)

    # Act
    with pytest.raises(BatchFileFormatError) as err:
        test_parser.parse(file, 100)

    # Assert
    assert err.match(r"Invalid data on line 3 \(TaskID 2\)")
    assert err.match(r"PatientName - This field may not be blank")
