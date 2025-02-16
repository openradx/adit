import factory
from faker import Faker
from pydicom.uid import generate_uid

from adit_server.core.factories import AbstractDicomJobFactory, AbstractDicomTaskFactory

from .models import BatchQueryJob, BatchQueryResult, BatchQueryTask

fake = Faker()

SERIES_NUMBER = ("+1", "2", "3", "+4", "5", "6", "7", "8")


class BatchQueryJobFactory(AbstractDicomJobFactory[BatchQueryJob]):
    class Meta:
        model = BatchQueryJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")


class BatchQueryTaskFactory(AbstractDicomTaskFactory[BatchQueryTask]):
    class Meta:
        model = BatchQueryTask

    job = factory.SubFactory(BatchQueryJobFactory)
    lines = factory.LazyFunction(lambda: [fake.pyint(min_value=2)])
    patient_id = factory.Faker("numerify", text="########")
    patient_name = factory.LazyFunction(lambda: f"{fake.last_name()}, {fake.first_name()}")
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    accession_number = factory.Faker("numerify", text="############")
    study_date_start = factory.Faker("date_between", start_date="-2y", end_date="-1y")
    study_date_end = factory.Faker("date_between", start_date="-1y", end_date="today")
    modalities = factory.Faker("random_elements", elements=("CT", "MR", "DX"), unique=True)
    study_description = factory.Faker("street_name")
    series_description = factory.Faker("street_name")
    series_numbers = factory.Faker("random_elements", elements=SERIES_NUMBER, unique=True)
    pseudonym = factory.Faker("pystr", min_chars=10, max_chars=10)


class BatchQueryResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchQueryResult

    job = factory.SubFactory(BatchQueryJobFactory)
    query = factory.SubFactory(BatchQueryTaskFactory)
    patient_id = factory.Faker("numerify", text="##########")
    patient_name = factory.LazyFunction(lambda: f"{fake.last_name()}, {fake.first_name()}")
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    accession_number = factory.Faker("ean")
    study_date = factory.Faker("date_between", start_date="-2y", end_date="today")
    study_time = factory.Faker("time_object")
    modalities = factory.Faker("random_elements", elements=("CT", "MR", "DX"), unique=True)
    image_count = factory.Faker("random_int", min=3, max=1500)
    study_description = factory.Faker("street_name")
    series_description = factory.Faker("street_name")
    series_number = factory.Faker("random_element", elements=SERIES_NUMBER)
    pseudonym = factory.Faker("pystr", min_chars=10, max_chars=10)
    study_uid = factory.LazyFunction(generate_uid)
    series_uid = factory.LazyFunction(generate_uid)
