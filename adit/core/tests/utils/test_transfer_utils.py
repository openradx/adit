from unittest.mock import patch, create_autospec, ANY
import datetime
import pytest
from django.db import connection
from django.db.utils import ProgrammingError
from django.db.models.base import ModelBase
from ...models import TransferJob, TransferTask
from ...factories import (
    DicomServerFactory,
    DicomFolderFactory,
    TransferJobFactory,
    TransferTaskFactory,
)
from ...utils.dicom_connector import DicomConnector
from ...utils.transfer_utils import execute_transfer


@pytest.fixture(scope="session")
def setup_abstract_models(django_db_setup, django_db_blocker):
    # Solution adapted from https://stackoverflow.com/q/4281670/166229
    with django_db_blocker.unblock():
        transfer_job_model = ModelBase(
            TransferJob.__name__,
            (TransferJob,),
            {"__module__": TransferJob.__module__},
        )
        transfer_task_model = ModelBase(
            TransferTask.__name__,
            (TransferTask,),
            {"__module__": TransferTask.__module__},
        )
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(transfer_job_model)
                schema_editor.create_model(transfer_task_model)
        except ProgrammingError:
            pass

        yield transfer_job_model, transfer_task_model

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(transfer_job_model)
            schema_editor.delete_model(transfer_task_model)

        connection.close()


@pytest.fixture(scope="session")
def setup_abstract_factories(setup_abstract_models):
    TestTransferJob, TestTransferTask = setup_abstract_models

    class TestTransferJobFactory(TransferJobFactory):
        class Meta:
            model = TestTransferJob

    class TestTransferTaskFactory(TransferTaskFactory):
        class Meta:
            model = TestTransferTask

    yield TestTransferJobFactory, TestTransferTaskFactory


@pytest.mark.django_db
def test_transfer_to_server_succeeds(setup_abstract_factories):
    # Arrange
    TestTransferJobFactory, TestTransferTaskFactory = setup_abstract_factories
    job = TestTransferJobFactory(
        status=TransferJob.Status.PENDING,
        source=DicomServerFactory(),
        destination=DicomServerFactory(),
        archive_password="",
    )
    task = TestTransferTaskFactory(
        status=TransferTask.Status.PENDING, series_uids=[], pseudonym=""
    )
    task.job = job
    study = {
        "PatientID": task.patient_id,
        "StudyInstanceUID": task.study_uid,
        "StudyDate": datetime.date(2020, 10, 1),
        "StudyTime": datetime.time(8, 0),
        "ModalitiesInStudy": ["CT", "SR"],
    }
    # transfer_util.source_connector = create_autospec(DicomConnector)
    # transfer_util.dest_connector = create_autospec(DicomConnector)
    # transfer_util.source_connector.find_studies.return_value = [study]

    # # Act
    # execute_transfer(task)

    # # Assert
    # transfer_util.source_connector.download_study.assert_called_with(
    #     task.patient_id, task.study_uid, ANY, modifier_callback=ANY
    # )
    # download_path = transfer_util.source_connector.download_study.call_args[0][2]
    # dt = f"{study['StudyDate'].strftime('%Y%m%d')}-{study['StudyTime'].strftime('%H%M%S')}"
    # expected_path = f"{study['PatientID']}/{dt}-{','.join(study['ModalitiesInStudy'])}"
    # assert download_path.match(expected_path)
    # upload_path = transfer_util.dest_connector.upload_folder.call_args[0][0]
    # assert upload_path.match(f"*/{study['PatientID']}")


# @pytest.mark.django_db
# @patch("adit.core.utils.transfer_util.Path.mkdir", autospec=True)
# def test_transfer_to_folder_succeeds(_, setup_abstract_factories):
#     # Arrange
#     TestTransferJobFactory, TestTransferTaskFactory = setup_abstract_factories
#     job = TestTransferJobFactory(
#         status=TransferJob.Status.PENDING,
#         source=DicomServerFactory(),
#         destination=DicomFolderFactory(),
#         archive_password="",
#     )
#     task = TestTransferTaskFactory(
#         status=TransferTask.Status.PENDING,
#         series_uids=[],
#         pseudonym="",
#     )
#     task.job = job
#     study = {
#         "PatientID": task.patient_id,
#         "StudyInstanceUID": task.study_uid,
#         "StudyDate": datetime.date(2020, 10, 1),
#         "StudyTime": datetime.time(8, 0),
#         "ModalitiesInStudy": ["CT", "SR"],
#     }
#     transfer_util.source_connector = create_autospec(DicomConnector)
#     transfer_util.source_connector.find_studies.return_value = [study]

#     # Act
#     transfer_task_status = execute_transfer(task)

#     # Assert
#     transfer_util.source_connector.download_study.assert_called_with(
#         task.patient_id, task.study_uid, ANY, modifier_callback=ANY
#     )
#     download_path = transfer_util.source_connector.download_study.call_args[0][2]
#     dt = f"{study['StudyDate'].strftime('%Y%m%d')}-{study['StudyTime'].strftime('%H%M%S')}"
#     expected_path = f"{study['PatientID']}/{dt}-{','.join(study['ModalitiesInStudy'])}"
#     assert download_path.match(expected_path)


# @pytest.mark.django_db
# @patch("subprocess.Popen")
# def test_transfer_to_archive_succeeds(Popen, setup_abstract_factories):
#     # Arrange
#     TestTransferJobFactory, TestTransferTaskFactory = setup_abstract_factories
#     job = TestTransferJobFactory(
#         status=TransferJob.Status.PENDING,
#         source=DicomServerFactory(),
#         destination=DicomFolderFactory(),
#         archive_password="mysecret",
#     )
#     task = TestTransferTaskFactory(
#         status=TransferTask.Status.PENDING, series_uids=[], pseudonym=""
#     )
#     task.job = job
#     study = {
#         "PatientID": task.patient_id,
#         "StudyInstanceUID": task.study_uid,
#         "StudyDate": datetime.date(2020, 10, 1),
#         "StudyTime": datetime.time(8, 0),
#         "ModalitiesInStudy": ["CT", "SR"],
#     }
#     transfer_util = TransferUtil(task)
#     transfer_util.source_connector = create_autospec(DicomConnector)
#     transfer_util.source_connector.find_studies.return_value = [study]
#     Popen().returncode = 0
#     Popen().communicate.return_value = ("", "")

#     # Act
#     status = execute_transfer(task)

#     # Assert
#     transfer_util.source_connector.download_study.assert_called_with(
#         task.patient_id, task.study_uid, ANY, modifier_callback=ANY
#     )
#     download_path = transfer_util.source_connector.download_study.call_args[0][2]
#     dt = f"{study['StudyDate'].strftime('%Y%m%d')}-{study['StudyTime'].strftime('%H%M%S')}"
#     assert download_path.match(
#         f"{study['PatientID']}/{dt}-{','.join(study['ModalitiesInStudy'])}"
#     )
#     assert Popen.call_args[0][0][0] == "7z"

# transfer_util.source_connector.download_study.assert_called_with(
#     task.patient_id, task.study_uid, ANY, modifier_callback=ANY
# )
# download_path = transfer_util.source_connector.download_study.call_args[0][2]
# dt = f"{study['StudyDate'].strftime('%Y%m%d')}-{study['StudyTime'].strftime('%H%M%S')}"
# expected_path = f"{study['PatientID']}/{dt}-{','.join(study['ModalitiesInStudy'])}"
# assert download_path.match(expected_path)
# upload_path = transfer_util.dest_connector.upload_folder.call_args[0][0]
# assert upload_path.match(f"*/{study['PatientID']}")
