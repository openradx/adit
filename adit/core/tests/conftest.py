import factory
import pytest
from django.db import connection, models

from ..factories import (
    AbstractDicomJobFactory,
    AbstractDicomTaskFactory,
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
)
from ..models import AppSettings, DicomJob, DicomTask, TransferJob, TransferTask


class ExampleAppSettings(AppSettings):
    class Meta:
        app_label = "adit.core"


class ExampleDicomJob(DicomJob):
    class Meta:
        app_label = "adit.core"


class ExampleDicomTask(DicomTask):
    class Meta:
        app_label = "adit.core"

    job = models.ForeignKey(ExampleDicomJob, on_delete=models.CASCADE, related_name="tasks")


class ExampleTransferJob(TransferJob):
    class Meta:
        app_label = "adit.core"


class ExampleTransferTask(TransferTask):
    class Meta:
        app_label = "adit.core"

    job = models.ForeignKey(ExampleTransferJob, on_delete=models.CASCADE, related_name="tasks")


class ExampleDicomJobFactory(AbstractDicomJobFactory[ExampleDicomJob]):
    class Meta:
        model = ExampleDicomJob


class ExampleDicomTaskFactory(AbstractDicomTaskFactory[ExampleDicomTask]):
    class Meta:
        model = ExampleDicomTask

    job = factory.SubFactory(ExampleDicomJobFactory)


class ExampleTransferJobFactory(AbstractTransferJobFactory[ExampleTransferJob]):
    class Meta:
        model = ExampleTransferJob


class ExampleTransferTaskFactory(AbstractTransferTaskFactory[ExampleTransferTask]):
    class Meta:
        model = ExampleTransferTask

    job = factory.SubFactory(ExampleTransferJobFactory)


class ExampleModels:
    app_settings_class = ExampleAppSettings
    dicom_job_class = ExampleDicomJob
    dicom_task_class = ExampleDicomTask
    transfer_job_class = ExampleTransferJob
    transfer_task_class = ExampleTransferTask
    dicom_job_factory_class = ExampleDicomJobFactory
    dicom_task_factory_class = ExampleDicomTaskFactory
    transfer_job_factory_class = ExampleTransferJobFactory
    transfer_task_factory_class = ExampleTransferTaskFactory


@pytest.fixture
def example_models(transactional_db):
    # TODO: Find out why we can't use a session or module fixture here.
    # Solution adapted from https://stackoverflow.com/q/4281670/166229
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(ExampleAppSettings)
        schema_editor.create_model(ExampleDicomJob)
        schema_editor.create_model(ExampleDicomTask)
        schema_editor.create_model(ExampleTransferJob)
        schema_editor.create_model(ExampleTransferTask)

    ExampleAppSettings.objects.create()

    yield ExampleModels

    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(ExampleAppSettings)
        schema_editor.delete_model(ExampleDicomJob)
        schema_editor.delete_model(ExampleDicomTask)
        schema_editor.delete_model(ExampleTransferJob)
        schema_editor.delete_model(ExampleTransferTask)
