import factory
from .models import BatchTransferJob
from main.factories import DicomServerFactory, DicomPathFactory
from accounts.factories import UserFactory

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
