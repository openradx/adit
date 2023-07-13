from typing import Generic, TypeVar

import factory
from faker import Faker

from adit.accounts.factories import UserFactory

from .models import (
    DicomFolder,
    DicomJob,
    DicomNode,
    DicomServer,
    DicomTask,
    TransferJob,
    TransferTask,
)

fake = Faker()

T = TypeVar("T")


class BaseDjangoModelFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, *args, **kwargs) -> T:
        return super().create(*args, **kwargs)


class AbstractDicomNodeFactory(Generic[T], BaseDjangoModelFactory[T]):
    class Meta:
        model: DicomNode

    name = factory.Faker("domain_word")
    source_active = True
    destination_active = True


class DicomServerFactory(AbstractDicomNodeFactory[DicomServer]):
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


class DicomWebServerFactory(DicomServerFactory):
    class Meta:
        model = DicomServer
        django_get_or_create = ("name",)

    ae_title = factory.Faker("pystr", min_chars=4, max_chars=12)
    host = factory.Faker("ipv4")
    port = factory.Faker("random_int", min=1, max=9999)

    patient_root_find_support = False
    patient_root_get_support = False
    patient_root_move_support = False
    study_root_find_support = False
    study_root_get_support = False
    study_root_move_support = False
    store_scp_support = False

    dicomweb_qido_support = True
    dicomweb_wado_support = True
    dicomweb_stow_support = True
    dicomweb_root_url = factory.Faker("url")


class DicomFolderFactory(AbstractDicomNodeFactory[DicomFolder]):
    class Meta:
        model = DicomFolder
        django_get_or_create = ("name",)

    path = factory.Faker("file_path")


job_status_keys = [key for key, value in TransferJob.Status.choices]


class AbstractDicomJobFactory(Generic[T], BaseDjangoModelFactory[T]):
    class Meta:
        model: DicomJob

    source = factory.SubFactory(DicomServerFactory)
    status = factory.Faker("random_element", elements=job_status_keys)
    message = factory.Faker("sentence")
    urgent = factory.Faker("boolean", chance_of_getting_true=25)
    owner = factory.SubFactory(UserFactory)


class AbstractTransferJobFactory(Generic[T], AbstractDicomJobFactory[T]):
    class Meta:
        model: TransferJob

    destination = factory.SubFactory(DicomServerFactory)
    trial_protocol_id = factory.Faker("word")
    trial_protocol_name = factory.Faker("text", max_nb_chars=25)


task_status_keys = [key for key, value in TransferTask.Status.choices]


class AbstractDicomTaskFactory(Generic[T], BaseDjangoModelFactory[T]):
    class Meta:
        model: DicomTask

    task_id = factory.Sequence(int)
    status = factory.Faker("random_element", elements=task_status_keys)
    message = factory.Faker("sentence")
    log = factory.Faker("paragraph")


def generate_uids():
    if fake.boolean(chance_of_getting_true=25):
        uids = [fake.uuid4() for _ in range(fake.random_int(min=1, max=8))]
        return ", ".join(uids)
    return ""


class AbstractTransferTaskFactory(Generic[T], AbstractDicomTaskFactory[T]):
    class Meta:
        model: TransferTask

    patient_id = factory.Faker("numerify", text="##########")
    study_uid = factory.Faker("uuid4")
    series_uids = factory.LazyFunction(generate_uids)
    pseudonym = factory.Faker("hexify", text="^^^^^^^^^^")
