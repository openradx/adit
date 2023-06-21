import factory
from faker import Faker

from adit.core.factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
)

from .models import ContinuousTransferJob, ContinuousTransferTask

fake = Faker()

SERIES_NUMBER = ("+1", "2", "3", "+4", "5", "6", "7", "8")


class ContinuousTransferJobFactory(AbstractTransferJobFactory[ContinuousTransferJob]):
    class Meta:
        model = ContinuousTransferJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")
    study_date_start = factory.Faker("date_between", start_date="-2y", end_date="-1y")
    study_date_end = factory.Faker("date_between", start_date="-1y", end_date="today")
    last_transfer = factory.Faker("date_between", start_date="-2y", end_date="today")
    patient_id = factory.Faker("numerify", text="########")
    patient_name = factory.LazyFunction(lambda: f"{fake.last_name()}, {fake.first_name()}")
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    modalities = factory.Faker("random_elements", elements=("CT", "MR", "DX"), unique=True)
    study_description = factory.Faker("street_name")
    series_description = factory.Faker("street_name")
    series_numbers = factory.Faker("random_elements", elements=SERIES_NUMBER, unique=True)


class ContinuousTransferTaskFactory(AbstractTransferTaskFactory[ContinuousTransferTask]):
    class Meta:
        model = ContinuousTransferTask

    job = factory.SubFactory(ContinuousTransferJobFactory)
