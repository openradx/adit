from datetime import timezone
from typing import Generic, TypeVar

import factory
from faker import Faker
from pydicom.uid import generate_uid

from .models import Report

T = TypeVar("T")

fake = Faker()


class BaseDjangoModelFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, *args, **kwargs) -> T:
        return super().create(*args, **kwargs)


class ReportFactory(BaseDjangoModelFactory[Report]):
    class Meta:
        model = Report

    document_id = factory.Faker("uuid4")
    pacs_aet = factory.Faker("word")
    pacs_name = factory.Faker("word")
    patient_id = factory.Faker("numerify", text="##########")
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    patient_sex = factory.Faker("random_element", elements=["F", "M", "U"])
    study_instance_uid = factory.LazyFunction(generate_uid)
    accession_number = factory.Faker("numerify", text="############")
    study_description = factory.Faker("sentence")
    study_datetime = factory.Faker("date_time_between", start_date="-10y", tzinfo=timezone.utc)
    series_instance_uid = factory.LazyFunction(generate_uid)
    modalities_in_study = factory.LazyFunction(
        lambda: fake.random_elements(elements=("CT", "MR", "DX", "PT", "US"), unique=True)
    )
    sop_instance_uid = factory.LazyFunction(generate_uid)
    references = factory.LazyFunction(lambda: [fake.url() for _ in range(fake.random_int(1, 3))])
    body = factory.Faker("paragraph")
