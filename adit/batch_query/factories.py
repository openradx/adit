import factory
from faker import Faker
from adit.core.factories import (
    DicomJobFactory,
    DicomTaskFactory,
)
from .models import BatchQueryJob, BatchQueryTask, BatchQueryResult


fake = Faker()


class BatchQueryJobFactory(DicomJobFactory):
    class Meta:
        model = BatchQueryJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")


class BatchQueryTaskFactory(DicomTaskFactory):
    class Meta:
        model = BatchQueryTask

    job = factory.SubFactory(BatchQueryJobFactory)
    patient_id = factory.Faker("numerify", text="########")
    patient_name = factory.LazyFunction(
        lambda: f"{fake.last_name()}, {fake.first_name()}"
    )
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    accession_number = factory.Faker("numerify", text="############")
    modalities = factory.Faker(
        "random_elements", elements=("CT", "MR", "DX"), unique=True
    )
    study_date_start = factory.Faker("date_between", start_date="-2y", end_date="-1y")
    study_date_end = factory.Faker("date_between", start_date="-1y", end_date="today")
    series_description = factory.Faker("street_name")


class BatchQueryResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchQueryResult

    job = factory.SubFactory(BatchQueryJobFactory)
    query = factory.SubFactory(BatchQueryTaskFactory)
    patient_id = factory.Faker("numerify", text="##########")
    patient_name = factory.LazyFunction(
        lambda: f"{fake.last_name()}, {fake.first_name()}"
    )
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    study_uid = factory.Faker("uuid4")
    accession_number = factory.Faker("ean")
    study_date = factory.Faker("date_between", start_date="-2y", end_date="today")
    study_time = factory.Faker("time_object")
    study_description = factory.Faker("street_name")
    modalities = factory.Faker(
        "random_elements", elements=("CT", "MR", "DX"), unique=True
    )
    image_count = factory.Faker("random_int", min=3, max=1500)
    series_uid = factory.Faker("uuid4")
    series_description = factory.Faker("street_name")
    series_number = factory.Faker("ean")

