from unittest.mock import create_autospec

import pytest
from pydicom.dataset import Dataset
from pynetdicom import Association
from pynetdicom.status import Status

from adit.core.factories import DicomServerFactory
from adit.core.utils.dicom_connector import DicomConnector


class DicomTestHelper:
    @staticmethod
    def create_dataset_from_dict(data):
        ds = Dataset()
        for i in data:
            setattr(ds, i, data[i])
        return ds

    @staticmethod
    def create_successful_c_find_responses(data_dicts):
        responses = []
        for data_dict in data_dicts:
            identifier = DicomTestHelper.create_dataset_from_dict(data_dict)
            pending_status = Dataset()
            pending_status.Status = Status.PENDING
            responses.append((pending_status, identifier))

        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        responses.append((success_status, None))

        return responses

    @staticmethod
    def create_successful_c_get_response():
        responses = []
        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        responses.append((success_status, None))
        return responses

    @staticmethod
    def create_successful_c_move_response():
        return DicomTestHelper.create_successful_c_get_response()

    @staticmethod
    def create_successful_c_store_response():
        success_status = Dataset()
        success_status.Status = Status.SUCCESS
        return success_status


@pytest.fixture
def dicom_test_helper():
    return DicomTestHelper


@pytest.fixture
def association():
    assoc = create_autospec(Association)
    assoc.is_established = True
    return assoc


@pytest.fixture
def dicom_connector(db):
    server = DicomServerFactory()
    return DicomConnector(server)
