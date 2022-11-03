from datetime import date
import pytest
from django.core.exceptions import ValidationError
from ..models import BatchQueryTask
from ..factories import BatchQueryTaskFactory


class TestBatchQueryTask:
    @pytest.mark.django_db
    def test_valid_with_only_patient_id(self):
        task: BatchQueryTask = BatchQueryTaskFactory()
        task.patient_id = "1001"
        task.patient_name = ""
        task.patient_birth_date = None

        try:
            task.clean()
        except ValidationError:
            pytest.fail()

    @pytest.mark.django_db
    def test_valid_with_patient_name_and_birth_date(self):
        task: BatchQueryTask = BatchQueryTaskFactory()
        task.patient_id = ""
        task.patient_name = "Apple, Peter"
        task.patient_birth_date = date(1976, 8, 31)

        try:
            task.clean()
        except ValidationError:
            pytest.fail()

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "patient_name,patient_birth_date",
        [("", None), ("Apple, Peter", None), ("", date(1976, 8, 31))],
    )
    def test_invalid_without_identfiable_patient(self, patient_name, patient_birth_date):
        task: BatchQueryTask = BatchQueryTaskFactory()
        task.patient_id = ""
        task.patient_name = patient_name
        task.patient_birth_date = patient_birth_date

        with pytest.raises(ValidationError):
            task.clean()
