import factory
from faker import Faker
from .models import BatchTransferJob, BatchTransferItem
from main.factories import DicomServerFactory, DicomPathFactory
from accounts.factories import UserFactory

fake = Faker()

status_keys = [key for key, value in BatchTransferJob.Status.choices]
class BatchTransferJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchTransferJob

    project_name = factory.Faker('sentence')
    project_description = factory.Faker('paragraph')
    source = factory.SubFactory(DicomServerFactory)
    destination = factory.SubFactory(DicomServerFactory)
    status = factory.Faker('random_element', elements=status_keys)
    created_by = factory.SubFactory(UserFactory)

class BatchTransferJobToPathFactory(BatchTransferJobFactory):
    destination = factory.SubFactory(DicomPathFactory)

status_codes = [key for key, value in BatchTransferItem.Status.choices]
class BatchTransferItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BatchTransferItem

    job = factory.SubFactory(BatchTransferJobFactory)
    row_id = factory.Sequence(lambda n: str(n))
    patient_id = factory.Faker('numerify', text='##########')
    patient_name = factory.LazyFunction(
            lambda: f'{fake.last_name()}, {fake.first_name}')
    patient_birth_date = factory.Faker('date_of_birth', minimum_age=15)
    study_date = factory.Faker('date_between', start_date='-2y', end_date='today')
    modality = factory.Faker('random_element', elements=('CT', 'MR', 'DX'))
    pseudonym = factory.Faker('lexify', text='????????',
            letters='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    status_code = factory.Faker('random_element', elements=status_codes)
    status_message = factory.Faker('sentence')