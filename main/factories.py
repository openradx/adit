import factory
from .models import DicomServer, DicomPath

class DicomServerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DicomServer
        django_get_or_create = ('node_id',)

    node_id = factory.Faker('hostname')
    node_name = factory.Faker('domain_word')
    ae_title = factory.Faker('pystr', min_chars=4, max_chars=12)
    ip = factory.Faker('ipv4')
    port = factory.Faker('random_int', min=1, max=9999)

class DicomPathFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DicomPath
        django_get_or_create = ('node_id', 'node_type')

    node_id = factory.Faker('hostname')
    node_name = factory.Faker('domain_word')
    path = factory.Faker('file_path')
