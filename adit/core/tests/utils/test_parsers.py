from io import StringIO
import pytest
from django.db import models
from ...models import DicomTask, BatchTask
from ...serializers import BatchTaskSerializer
from ...utils.parsers import BatchTaskParser, BatchTaskParserError


@pytest.fixture
def data():
    return [
        ["Batch ID", "Patient Name"],
        ["1", "Apple, Annie"],
        ["2", "Coconut, Coco"],
    ]


@pytest.fixture(scope="session")
def create_csv_file():
    def _create_csv_file(csv_data):
        csv_str = ""
        for row in csv_data:
            csv_str += ";".join(row) + "\n"
        return StringIO(csv_str)

    return _create_csv_file


@pytest.fixture(scope="session")
def parser():
    class TestTask(BatchTask):
        patient_name = models.CharField(max_length=324)

    class TestSerializer(BatchTaskSerializer):
        class Meta(BatchTaskSerializer.Meta):
            model = TestTask
            fields = ["batch_id", "patient_name"]

    return BatchTaskParser(
        TestSerializer,
        {
            "batch_id": "Batch ID",
            "patient_name": "Patient Name",
        },
    )


def test_valid_csv_file_is_parsed(create_csv_file, data, parser):
    # Arrange
    file = create_csv_file(data)

    # Act
    tasks = parser.parse(file)

    # Assert
    assert tasks[0].batch_id == int(data[1][0])
    assert tasks[1].batch_id == int(data[2][0])
    assert tasks[0].patient_name == data[1][1]
    assert tasks[1].patient_name == data[2][1]


def test_invalid_csv_file_raises(create_csv_file, data, parser):
    # Arrange
    data[2][1] = ""
    file = create_csv_file(data)

    # Act
    with pytest.raises(BatchTaskParserError) as err:
        parser.parse(file)

    # Assert
    assert err.match(r"Invalid data on line 3 \(Batch ID 2\)")
    assert err.match(r"Patient Name - This field may not be blank")
