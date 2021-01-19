from io import StringIO
import pytest
from django.db import models
from ...models import BatchTask
from ...serializers import BatchTaskSerializer
from ...utils.batch_parsers import BatchFileParser, ParsingError


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
        ["BatchID", "PatientName"],
        ["1", "Apple, Annie"],
        ["2", "Coconut, Coco"],
    ]


@pytest.fixture
def field_to_column_mapping():
    return {
        "batch_id": "BatchID",
        "patient_name": "PatientName",
    }


@pytest.fixture(scope="session")
def test_serializer_class():
    class TestTask(BatchTask):
        patient_name = models.CharField(max_length=324)

    class TestSerializer(BatchTaskSerializer):
        class Meta(BatchTaskSerializer.Meta):
            model = TestTask
            fields = ["batch_id", "patient_name"]

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
    tasks = test_parser.parse(file)

    # Assert
    assert tasks[0].batch_id == int(data[1][0])
    assert tasks[1].batch_id == int(data[2][0])
    assert tasks[0].patient_name == data[1][1]
    assert tasks[1].patient_name == data[2][1]


def test_invalid_model_data_raises(create_csv_file, data, test_parser):
    # Arrange
    data[2][1] = ""
    file = create_csv_file(data)

    # Act
    with pytest.raises(ParsingError) as err:
        test_parser.parse(file)

    # Assert
    assert err.match(r"Invalid data on line 3 \(BatchID 2\)")
    assert err.match(r"PatientName - This field may not be blank")
