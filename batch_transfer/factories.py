import factory
from faker import Faker
from main.factories import DicomServerFactory, DicomFolderFactory
from accounts.factories import UserFactory
from .models import BatchTransferJob, BatchTransferRequest

fake = Faker()

status_keys = [key for key, value in BatchTransferJob.Status.choices]


class BatchTransferJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchTransferJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")
    source = factory.SubFactory(DicomServerFactory)
    destination = factory.SubFactory(DicomServerFactory)
    status = factory.Faker("random_element", elements=status_keys)
    created_by = factory.SubFactory(UserFactory)


class BatchTransferJobToPathFactory(BatchTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)


status_codes = [key for key, value in BatchTransferRequest.Status.choices]


class BatchTransferRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchTransferRequest

    job = factory.SubFactory(BatchTransferJobFactory)
    request_id = factory.Sequence(str)
    patient_id = factory.Faker("numerify", text="##########")
    patient_name = factory.LazyFunction(
        lambda: f"{fake.last_name()}, {fake.first_name()}"
    )
    patient_birth_date = factory.Faker("date_of_birth", minimum_age=15)
    study_date = factory.Faker("date_between", start_date="-2y", end_date="today")
    modality = factory.Faker("random_element", elements=("CT", "MR", "DX"))
    pseudonym = factory.Faker(
        "lexify", text="????????", letters="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    status = factory.Faker("random_element", elements=status_codes)
    message = factory.Faker("sentence")
