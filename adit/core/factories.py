import factory
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.factories import BaseDjangoModelFactory
from faker import Faker
from pydicom.uid import generate_uid

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


class AbstractDicomNodeFactory[T](BaseDjangoModelFactory[T]):
    class Meta:
        model: DicomNode

    name = factory.Faker("domain_word")


def random_dicom_node_factory():
    return fake.random_element(elements=[DicomServerFactory, DicomFolderFactory])


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


class DicomMoveServerFactory(DicomServerFactory):
    patient_root_get_support = False
    study_root_get_support = False


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


class AbstractDicomJobFactory[T](BaseDjangoModelFactory[T]):
    class Meta:
        model: DicomJob

    status = factory.Faker("random_element", elements=job_status_keys)
    message = factory.Faker("sentence")
    urgent = factory.Faker("boolean", chance_of_getting_true=25)
    owner = factory.SubFactory(UserFactory)


class AbstractTransferJobFactory[T](AbstractDicomJobFactory[T]):
    class Meta:
        model: TransferJob

    trial_protocol_id = factory.Faker("word")
    trial_protocol_name = factory.Faker("text", max_nb_chars=25)


task_status_keys = [key for key, value in TransferTask.Status.choices]


class AbstractDicomTaskFactory[T](BaseDjangoModelFactory[T]):
    class Meta:
        model: DicomTask

    source = factory.SubFactory(DicomServerFactory)
    status = factory.Faker("random_element", elements=task_status_keys)
    message = factory.Faker("sentence")
    log = factory.Faker("paragraph")


def generate_uids():
    if fake.boolean(chance_of_getting_true=25):
        return [generate_uid() for _ in range(fake.random_int(min=1, max=8))]
    return []


class AbstractTransferTaskFactory[T](AbstractDicomTaskFactory[T]):
    class Meta:
        model: TransferTask

    destination = factory.SubFactory(DicomServerFactory)
    patient_id = factory.Faker("numerify", text="##########")
    study_uid = factory.LazyFunction(generate_uid)
    series_uids = factory.LazyFunction(generate_uids)
    pseudonym = factory.Faker("hexify", text="^^^^^^^^^^")
