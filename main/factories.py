import factory
from .models import DicomServer, DicomFolder

class DicomServerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DicomServer
        django_get_or_create = ('node_name',)

    node_name = factory.Faker('domain_word')
    ae_title = factory.Faker('pystr', min_chars=4, max_chars=12)
    ip = factory.Faker('ipv4')
    port = factory.Faker('random_int', min=1, max=9999)

class DicomFolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DicomFolder
        django_get_or_create = ('node_name',)

    node_name = factory.Faker('domain_word')
    path = factory.Faker('file_path')
