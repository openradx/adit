# import pytest
# from django.contrib.contenttypes.models import ContentType
# from pytest_mock import MockerFixture

# from ..factories import DicomServerFactory
# from ..models import DicomJob, DicomTask, QueuedTask
# from ..tasks import ProcessDicomJob
# from .conftest import ExampleModels


# class TestProcessDicomJob:
#     @pytest.mark.parametrize("urgent", [True, False])
#     def test_run_succeeds(self, urgent, mocker: MockerFixture, example_models: ExampleModels):
#         # Arrange
#         dicom_job = example_models.dicom_job_factory_class.create(
#             status=DicomJob.Status.PENDING,
#         )
#         dicom_task = example_models.dicom_task_factory_class.create(
#             status=DicomTask.Status.PENDING,
#             source=DicomServerFactory(),
#             job=dicom_job,
#         )

#         default_priority = 2
#         urgent_priority = 4

#         process_dicom_job = ProcessDicomJob()
#         process_dicom_job.dicom_job_class = example_models.dicom_job_class
#         process_dicom_job.default_priority = default_priority
#         process_dicom_job.urgent_priority = urgent_priority

#         # Act
#         process_dicom_job.run(dicom_job.id)

#         # Assert
#         queued_task = QueuedTask.objects.first()
#         assert queued_task is not None

#         # Some we can't assert content_object directly, maybe because of
#         # our example models. So we assert indirectly.
#         content_type = ContentType.objects.get_for_model(dicom_task)
#         assert queued_task.content_type.id == content_type.id
#         assert queued_task.object_id == dicom_task.id

#         assert queued_task.priority == urgent_priority if urgent else default_priority
