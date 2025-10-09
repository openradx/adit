from unittest.mock import patch

import pytest
import time_machine
from django.utils import timezone

from adit.core.models import DicomJob, DicomTask
from adit.core.tests.example_app.factories import (
    ExampleTransferJobFactory,
    ExampleTransferTaskFactory,
)


class TestDicomJob:
    @pytest.mark.django_db
    def test_job_post_process_all_tasks_succeed(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

        result = job.post_process()

        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.SUCCESS
        assert job.message == "All tasks succeeded."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_some_tasks_fail(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

        result = job.post_process()
        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.FAILURE
        assert job.message == "Some tasks failed."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_all_tasks_fail(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)

        result = job.post_process()
        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.FAILURE
        assert job.message == "All tasks failed."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_tasks_still_pending(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.PENDING)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)

        result = job.post_process()
        job.refresh_from_db()

        assert result is False  # Job is not finished
        assert job.status == DicomJob.Status.PENDING
        assert job.end is None

    @pytest.mark.django_db
    def test_job_post_process_tasks_in_progress(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.IN_PROGRESS)

        result = job.post_process()
        job.refresh_from_db()

        assert result is False
        assert job.status == DicomJob.Status.IN_PROGRESS
        assert job.end is None

    @pytest.mark.django_db
    def test_job_post_process_all_tasks_warning(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.WARNING)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.WARNING)

        result = job.post_process()
        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.WARNING
        assert job.message == "All tasks have warnings."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_success_and_warning(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.WARNING)

        result = job.post_process()
        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.WARNING
        assert job.message == "Some tasks have warnings."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_warning_and_failure(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.WARNING)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)

        result = job.post_process()
        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.FAILURE
        assert job.message == "Some tasks failed."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_success_warning_failure(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        # Mix of all states
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.WARNING)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)

        result = job.post_process()
        job.refresh_from_db()

        assert result is True
        assert job.status == DicomJob.Status.FAILURE
        assert job.message == "Some tasks failed."
        assert job.end is not None

    @pytest.mark.django_db
    def test_job_post_process_canceling_status(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.CANCELING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)

        result = job.post_process()
        job.refresh_from_db()

        assert result is False  # Canceling doesn't count as finished
        assert job.status == DicomJob.Status.CANCELED
        assert job.end is None

    @pytest.mark.django_db
    @time_machine.travel("2025-01-15 14:30:00+00:00")
    def test_job_timezone_correctness(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)

        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

        job.post_process()
        job.refresh_from_db()

        expected_time = timezone.now()
        assert job.end is not None
        assert abs((job.end - expected_time).total_seconds()) < 1

    @pytest.mark.django_db
    @time_machine.travel("2025-03-20 09:15:30+01:00")
    def test_job_timezone_with_different_timezone(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
        ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

        job.post_process()
        job.refresh_from_db()

        assert job.end is not None
        expected_time = timezone.now()
        assert abs((job.end - expected_time).total_seconds()) < 1

    @pytest.mark.django_db
    def test_job_post_process_sends_email_when_enabled(self):
        with patch("adit.core.models.send_job_finished_mail") as mock_send_mail:
            job = ExampleTransferJobFactory.create(
                status=DicomJob.Status.PENDING, send_finished_mail=True
            )
            ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

            result = job.post_process()

            assert result is True
            mock_send_mail.assert_called_once_with(job)

    @pytest.mark.django_db
    def test_job_post_process_does_not_send_email_when_disabled(self):
        with patch("adit.core.models.send_job_finished_mail") as mock_send_mail:
            job = ExampleTransferJobFactory.create(
                status=DicomJob.Status.PENDING, send_finished_mail=False
            )
            ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

            result = job.post_process()

            assert result is True
            mock_send_mail.assert_not_called()

    @pytest.mark.django_db
    def test_job_post_process_suppress_email(self):
        with patch("adit.core.models.send_job_finished_mail") as mock_send_mail:
            job = ExampleTransferJobFactory.create(
                status=DicomJob.Status.PENDING, send_finished_mail=True
            )
            ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

            result = job.post_process(suppress_email=True)

            assert result is True
            mock_send_mail.assert_not_called()

    @pytest.mark.django_db
    def test_job_properties(self):
        job = ExampleTransferJobFactory.create(status=DicomJob.Status.UNVERIFIED)
        assert not job.is_verified
        assert job.is_deletable

        job.status = DicomJob.Status.PENDING
        assert job.is_verified
        assert job.is_cancelable
        assert not job.is_resumable
        assert not job.is_retriable
        assert not job.is_restartable

        job.status = DicomJob.Status.IN_PROGRESS
        assert job.is_cancelable

        job.status = DicomJob.Status.CANCELED
        assert job.is_resumable
        assert job.is_restartable

        job.status = DicomJob.Status.FAILURE
        assert job.is_retriable
        assert job.is_restartable

        job.status = DicomJob.Status.SUCCESS
        assert job.is_restartable

    @pytest.mark.django_db
    def test_job_processed_tasks_property(self):
        job = ExampleTransferJobFactory.create()

        pending_task = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.PENDING)
        in_progress_task = ExampleTransferTaskFactory.create(
            job=job, status=DicomTask.Status.IN_PROGRESS
        )
        success_task = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
        failure_task = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.FAILURE)
        warning_task = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.WARNING)
        canceled_task = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.CANCELED)

        processed_tasks = job.processed_tasks

        assert pending_task not in processed_tasks
        assert in_progress_task not in processed_tasks

        assert success_task in processed_tasks
        assert failure_task in processed_tasks
        assert warning_task in processed_tasks
        assert canceled_task in processed_tasks

        assert processed_tasks.count() == 4


class TestDicomTask:
    @pytest.mark.django_db
    def test_task_properties(self):
        task = ExampleTransferTaskFactory.create(status=DicomTask.Status.PENDING)
        assert task.is_deletable
        assert not task.is_resettable
        assert not task.is_killable

        task.status = DicomTask.Status.IN_PROGRESS
        assert not task.is_deletable
        assert not task.is_resettable
        assert task.is_killable

        task.status = DicomTask.Status.SUCCESS
        assert not task.is_deletable
        assert task.is_resettable
        assert not task.is_killable

        task.status = DicomTask.Status.FAILURE
        assert not task.is_deletable
        assert task.is_resettable
        assert not task.is_killable

        task.status = DicomTask.Status.WARNING
        assert not task.is_deletable
        assert task.is_resettable
        assert not task.is_killable

        task.status = DicomTask.Status.CANCELED
        assert not task.is_deletable
        assert task.is_resettable
        assert not task.is_killable

    @pytest.mark.django_db
    def test_task_string_representation(self):
        task = ExampleTransferTaskFactory.create()
        expected = f"ExampleTransferTask [{task.pk}]"
        assert str(task) == expected
