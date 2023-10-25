from datetime import date

import pytest

from ..serializers import BatchQueryTaskSerializer


@pytest.fixture
def data():
    return [
        {
            "lines": [1, 2],
            "patient_id": "1001",
            "study_date_start": "2019-06-03",
            "study_date_end": "2019-06-05",
            "modalities": ["CT", "SR"],
        },
        {
            "lines": [1, 2],
            "patient_name": "Coconut^Coco",
            "patient_birth_date": "1976-12-09",
            "modalities": ["CT"],
        },
        {
            "lines": [1, 2],
            "patient_id": "1003",
            "accession_number": "0062094311",
        },
    ]


def test_deserializes_query_task(data):
    # Act
    serializer = BatchQueryTaskSerializer(data=data, many=True)

    # Assert
    assert serializer.is_valid()

    assert isinstance(serializer.validated_data, list)

    assert serializer.validated_data[0]["study_date_start"] == date(2019, 6, 3)
    assert serializer.validated_data[0]["study_date_end"] == date(2019, 6, 5)
    assert serializer.validated_data[0]["modalities"] == ["CT", "SR"]

    assert serializer.validated_data[1]["patient_name"] == "Coconut^Coco"
    assert serializer.validated_data[1]["patient_birth_date"] == date(1976, 12, 9)
    assert serializer.validated_data[1]["modalities"] == ["CT"]

    assert serializer.validated_data[2]["patient_id"] == "1003"
    assert serializer.validated_data[2]["accession_number"] == "0062094311"
