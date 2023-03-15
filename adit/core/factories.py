import factory
from faker import Faker

from adit.accounts.factories import UserFactory

from .models import DicomFolder, DicomServer, TransferJob, TransferTask

fake = Faker()


class DicomNodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = None

    name = factory.Faker("domain_word")
    source_active = True
    destination_active = True


class DicomServerFactory(DicomNodeFactory):
    class Meta:
        model = DicomServer
        django_get_or_create = ("name",)

    ae_title = factory.Faker("pystr", min_chars=4, max_chars=12)
    host = factory.Faker("ipv4")
    port = factory.Faker("random_int", min=1, max=9999)

    patient_root_find_support = True
    patient_root_get_support = True
    patient_root_move_support = True
    study_root_find_support = True
    study_root_get_support = True
    study_root_move_support = True
    store_scp_support = True


class DicomFolderFactory(DicomNodeFactory):
    class Meta:
        model = DicomFolder
        django_get_or_create = ("name",)

    path = factory.Faker("file_path")


job_status_keys = [key for key, value in TransferJob.Status.choices]


class DicomJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = None

    source = factory.SubFactory(DicomServerFactory)
    status = factory.Faker("random_element", elements=job_status_keys)
    message = factory.Faker("sentence")
    urgent = factory.Faker("boolean", chance_of_getting_true=25)
    owner = factory.SubFactory(UserFactory)


class TransferJobFactory(DicomJobFactory):
    class Meta:
        model = None

    destination = factory.SubFactory(DicomServerFactory)
    trial_protocol_id = factory.Faker("word")
    trial_protocol_name = factory.Faker("text", max_nb_chars=25)


task_status_keys = [key for key, value in TransferTask.Status.choices]


class DicomTaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = None

    task_id = factory.Sequence(int)
    status = factory.Faker("random_element", elements=task_status_keys)
    message = factory.Faker("sentence")
    log = factory.Faker("paragraph")


def generate_uids():
    if fake.boolean(chance_of_getting_true=25):
        return [fake.uuid4() for _ in range(fake.random_int(min=1, max=8))]
    return None


class TransferTaskFactory(DicomTaskFactory):
    class Meta:
        model = None

    patient_id = factory.Faker("numerify", text="##########")
    study_uid = factory.Faker("uuid4")
    series_uids = factory.LazyFunction(generate_uids)
    pseudonym = factory.Faker("hexify", text="^^^^^^^^^^")
