from datetime import date
import pytest
from ..serializers import BatchQueryTaskSerializer


@pytest.fixture
def data():
    return [
        {
            "batch_id": "1",
            "patient_id": "1001",
            "study_date_start": "03.06.2019",
            "study_date_end": "05.06.2019",
            "modalities": "CT, SR",
        },
        {
            "batch_id": "2",
            "patient_name": "Coconut, Coco",
            "patient_birth_date": "09.12.1976",
            "modalities": "CT",
        },
        {
            "batch_id": "3",
            "patient_id": "1003",
            "accession_number": "0062094311",
        },
    ]


def test_deserializes_query_task(data):
    # Act
    serializer = BatchQueryTaskSerializer(data=data, many=True)

    # Assert
    assert serializer.is_valid()

    assert serializer.validated_data[0]["batch_id"] == 1
    assert serializer.validated_data[0]["study_date_start"] == date(2019, 6, 3)
    assert serializer.validated_data[0]["study_date_end"] == date(2019, 6, 5)
    assert serializer.validated_data[0]["modalities"] == ["CT", "SR"]

    assert serializer.validated_data[1]["patient_name"] == "Coconut^Coco"
    assert serializer.validated_data[1]["patient_birth_date"] == date(1976, 12, 9)
    assert serializer.validated_data[1]["modalities"] == ["CT"]

    assert serializer.validated_data[2]["patient_id"] == "1003"
    assert serializer.validated_data[2]["accession_number"] == "0062094311"
