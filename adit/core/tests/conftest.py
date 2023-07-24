import factory
import pytest
from django.db import connection, models

from ..factories import TransferJobFactory, TransferTaskFactory
from ..models import AppSettings, TransferJob, TransferTask


class DummyTransferSettings(AppSettings):
    class Meta:
        app_label = "adit.core"


class DummyTransferJob(TransferJob):
    class Meta:
        app_label = "adit.core"


class DummyTransferTask(TransferTask):
    class Meta:
        app_label = "adit.core"

    job = models.ForeignKey(DummyTransferJob, on_delete=models.CASCADE, related_name="tasks")


class DummyTransferJobFactory(TransferJobFactory):
    class Meta:
        model = DummyTransferJob


class DummyTransferTaskFactory(TransferTaskFactory):
    class Meta:
        model = DummyTransferTask

    job = factory.SubFactory(DummyTransferJobFactory)


# @pytest.fixture
# def setup_test_models(transactional_db):
#     # TODO: Find out why we can't use a session or module fixture here.
#     # Solution adapted from https://stackoverflow.com/q/4281670/166229
#     with connection.schema_editor() as schema_editor:
#         schema_editor.create_model(DummyTransferJob)
#         schema_editor.create_model(DummyTransferTask)

#     yield

#     with connection.schema_editor() as schema_editor:
#         schema_editor.delete_model(DummyTransferJob)
#         schema_editor.delete_model(DummyTransferTask)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker, transactional_db):
    # with django_db_blocker.unblock():
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(DummyTransferSettings)
        schema_editor.create_model(DummyTransferJob)
        schema_editor.create_model(DummyTransferTask)

    # yield

    # with django_db_blocker.unblock():
    #     with connection.schema_editor() as schema_editor:
    #         schema_editor.delete_model(DummyTransferSettings)
    #         schema_editor.delete_model(DummyTransferJob)
    #         schema_editor.delete_model(DummyTransferTask)
