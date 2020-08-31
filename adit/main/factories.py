import factory
from faker import Faker
from adit.accounts.factories import UserFactory
from .models import DicomServer, DicomFolder, TransferJob, TransferTask

fake = Faker()


class DicomServerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DicomServer
        django_get_or_create = ("node_name",)

    node_name = factory.Faker("domain_word")
    ae_title = factory.Faker("pystr", min_chars=4, max_chars=12)
    host = factory.Faker("ipv4")
    port = factory.Faker("random_int", min=1, max=9999)


class DicomFolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DicomFolder
        django_get_or_create = ("node_name",)

    node_name = factory.Faker("domain_word")
    path = factory.Faker("file_path")


job_status_keys = [key for key, value in TransferJob.Status.choices]


def generate_archive_password():
    if fake.boolean(chance_of_getting_true=25):
        return fake.word()

    return None


class TransferJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TransferJob

    source = factory.SubFactory(DicomServerFactory)
    destination = factory.SubFactory(DicomServerFactory)
    status = factory.Faker("random_element", elements=job_status_keys)
    message = factory.Faker("sentence")
    trial_protocol_id = factory.Faker("word")
    trial_protocol_name = factory.Faker("text", max_nb_chars=25)
    archive_password = factory.LazyFunction(generate_archive_password)
    created_by = factory.SubFactory(UserFactory)


task_status_keys = [key for key, value in TransferTask.Status.choices]


def generate_uids():
    if fake.boolean(chance_of_getting_true=25):
        return [fake.uuid4() for _ in range(fake.random_int(min=1, max=8))]

    return None


class TransferTaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TransferTask

    job = factory.SubFactory(TransferJobFactory)
    patient_id = factory.Faker("numerify", text="##########")
    study_uid = factory.Faker("uuid4")
    series_uids = factory.LazyFunction(generate_uids)
    pseudonym = factory.Faker("hexify", text="^^^^^^^^^^")
    status = factory.Faker("random_element", elements=task_status_keys)
    message = factory.Faker("sentence")
