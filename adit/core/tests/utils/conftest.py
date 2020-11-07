from unittest.mock import create_autospec
import pytest
from faker import Faker
from pydicom.dataset import Dataset
from pynetdicom.association import Association
from pynetdicom.status import Status
from adit.core.models import TransferTask
from adit.core.utils.dicom_connector import DicomConnector

fake = Faker()


class FakeDicomConnector(DicomConnector):
    def __init__(self, config=None, assoc_mock=None):
        if not config:
            config = DicomConnector.Config(
                client_ae_title="CLIENT_AE_TITLE",
                server_ae_title="SERVER_AE_TITLE",
                server_host="127.0.0.1",
                server_port=104,
            )

        if assoc_mock:
            self.assoc_mock = assoc_mock
        else:
            self.assoc_mock = create_autospec(Association)

        super().__init__(config)

    def _associate(self):
        self.assoc = self.assoc_mock

    def close_connection(self):
        self.assoc = None


class DicomHelper:
    @staticmethod
    def create_fake_dicom_connector(config=None, assoc_mock=None):
        return FakeDicomConnector(config, assoc_mock)

    @staticmethod
    def create_dataset_from_dict(data):
        ds = Dataset()
        for i in data:
            setattr(ds, i, data[i])
        return ds

    @staticmethod
    def create_study_dataset_from_task(task: TransferTask):
        ds = Dataset()
        ds.PatientID = task.patient_id
        ds.PatientName = fake.name().strip().replace(" ", "^")
        ds.PatientBirthDate = fake.date_of_birth()
        ds.AccessionNumber = fake.ssn()
        ds.StudyInstanceUID = task.study_uid
        ds.StudyDate = fake.date_between(start_date="-10y")
        ds.StudyTime = fake.time_object()
        ds.StudyDescription = fake.text(max_nb_chars=20)
        ds.NumberOfStudyRelatedInstances = fake.random_int(min=1, max=2000)
        ds.ModalitiesInStudy = fake.random_choices(elements=("CT", "MR"))
        return ds

    @staticmethod
    def create_c_find_responses(datasets):
        responses = []
        for identifier in datasets:
            pending_status = Dataset()
            pending_status.Status = Status.PENDING
            responses.append((pending_status, identifier))

        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        responses.append((success_status, None))

        return responses

    @staticmethod
    def create_c_get_responses():
        responses = []
        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        responses.append((success_status, None))
        return responses

    @staticmethod
    def create_c_store_response():
        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        return success_status


@pytest.fixture
def dicom_helper():
    return DicomHelper
