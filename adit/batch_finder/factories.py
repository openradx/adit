import factory
from faker import Faker
from adit.core.factories import (
    DicomJobFactory,
    BatchTaskFactory,
)
from .models import BatchFinderJob, BatchFinderQuery, BatchFinderResult


fake = Faker()


class BatchFinderJobFactory(DicomJobFactory):
    class Meta:
        model = BatchFinderJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")


class BatchFinderQueryFactory(BatchTaskFactory):
    class Meta:
        model = BatchFinderQuery

    job = factory.SubFactory(BatchFinderJobFactory)
    patient_id = factory.Faker("numerify", text="##########")
    patient_name = factory.LazyFunction(
        lambda: f"{fake.last_name()}, {fake.first_name()}"
    )
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    modalities = factory.Faker(
        "random_elements", elements=("CT", "MR", "DX"), unique=True
    )
    study_date_start = factory.Faker("date_between", start_date="-2y", end_date="-1y")
    study_date_end = factory.Faker("date_between", start_date="-1y", end_date="today")


class BatchFinderResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchFinderResult

    job = factory.SubFactory(BatchFinderJobFactory)
    query = factory.SubFactory(BatchFinderQueryFactory)
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
