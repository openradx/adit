import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from io import BytesIO
from pathlib import Path
from stat import S_IFREG
from typing import Any, AsyncGenerator, cast

from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.views import BaseUpdatePreferencesView
from adrf.views import sync_to_async
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import BadRequest
from django.http import StreamingHttpResponse
from django.urls import reverse_lazy
from pydicom import Dataset
from requests import HTTPError
from rest_framework.exceptions import NotFound
from stream_zip import NO_COMPRESSION_64, async_stream_zip

from adit.core.errors import DicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import write_dataset
from adit.core.utils.sanitize import sanitize_filename
from adit.core.views import (
    DicomJobCancelView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomJobVerifyView,
    DicomTaskDeleteView,
    DicomTaskDetailView,
    DicomTaskKillView,
    DicomTaskResetView,
    TransferJobListView,
)

from .filters import SelectiveTransferJobFilter, SelectiveTransferTaskFilter
from .forms import SelectiveTransferJobForm
from .mixins import SelectiveTransferLockedMixin
from .models import SelectiveTransferJob, SelectiveTransferTask
from .tables import SelectiveTransferJobTable, SelectiveTransferTaskTable

SELECTIVE_TRANSFER_SOURCE = "selective_transfer_source"
SELECTIVE_TRANSFER_DESTINATION = "selective_transfer_destination"
SELECTIVE_TRANSFER_URGENT = "selective_transfer_urgent"
SELECTIVE_TRANSFER_SEND_FINISHED_MAIL = "selective_transfer_send_finished_mail"
SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED = "selective_transfer_advanced_options_collapsed"

logger = logging.getLogger(__name__)


class SelectiveTransferUpdatePreferencesView(
    SelectiveTransferLockedMixin, BaseUpdatePreferencesView
):
    allowed_keys = [
        SELECTIVE_TRANSFER_SOURCE,
        SELECTIVE_TRANSFER_DESTINATION,
        SELECTIVE_TRANSFER_URGENT,
        SELECTIVE_TRANSFER_SEND_FINISHED_MAIL,
        SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED,
    ]


def download_study(request, server_id, patient_id, study_uid, pseudonymize, callback):
    try:
        server = DicomServer.objects.accessible_by_user(request.user, "source").get(id=server_id)
        operator = DicomOperator(server)

        exclude_modalities = settings.EXCLUDE_MODALITIES
        # TODO: Add condition for specified series_uids
        # when user selects specific series in a selected study
        if pseudonymize and exclude_modalities:
            series_list = list(
                operator.find_series(
                    QueryDataset.create(PatientID=patient_id, StudyInstanceUID=study_uid)
                )
            )
            for series in series_list:
                series_uid = series.SeriesInstanceUID
                modality = series.Modality
                if modality in exclude_modalities:
                    continue

                operator.fetch_series(patient_id, study_uid, series_uid, callback)
        else:
            operator.fetch_study(
                patient_id=patient_id,
                study_uid=study_uid,
                callback=callback,
            )
    # Raise NotFound error if specified DicomServer is not accessible
    except DicomServer.DoesNotExist:
        raise NotFound("Invalid DICOM server.")
    # Re-raise DicomErrors/HttpErrors from fetch_study
    except (DicomError, HTTPError):
        raise
    # If download_study fails before streaming happens, we can return a http response with the error
    except Exception as err:
        raise HTTPError(500, f"Unexpected error: {err}")


@login_required
@permission_required("selective_transfer.can_download_study")
async def selective_transfer_download_study_view(
    request: AuthenticatedHttpRequest,
    server_id: str | None = None,
    patient_id: str | None = None,
    study_uid: str | None = None,
) -> StreamingHttpResponse:
    pseudonym = request.GET.get("pseudonym")
    trial_protocol_id = request.GET.get("trial_protocol_id")
    trial_protocol_name = request.GET.get("trial_protocol_name")
    study_modalities = request.GET.get("study_modalities")
    study_date = request.GET.get("study_date")
    study_time = request.GET.get("study_time")

    download_folder = Path(f"study_download_{study_uid}")
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue[Dataset | None]()
    executor = ThreadPoolExecutor()
    dicom_manipulator = DicomManipulator()

    modifier = partial(
        dicom_manipulator.manipulate,
        pseudonym=pseudonym,
        trial_protocol_id=trial_protocol_id,
        trial_protocol_name=trial_protocol_name,
    )

    def callback(ds: Dataset) -> None:
        modifier(ds)
        # Schedules a task on the event loop that puts the dataset into the async queue
        loop.call_soon_threadsafe(queue.put_nowait, ds)

    fetch_task = asyncio.create_task(
        sync_to_async(download_study, thread_sensitive=False)(
            request=request,
            server_id=server_id,
            patient_id=patient_id,
            study_uid=study_uid,
            pseudonymize=bool(pseudonym),
            callback=callback,
        )
    )
    fetch_error: Exception | None = None

    async def add_sentinel_when_done():
        nonlocal fetch_error
        try:
            await fetch_task
        # Catch any error raised by download_study
        except Exception as err:
            fetch_error = err
        finally:
            await queue.put(None)

    asyncio.create_task(add_sentinel_when_done())

    # Synchronous blocking function
    def ds_to_buffer(ds):
        # TODO: Construct correct file path for instances in study
        if pseudonym:
            patient_folder = download_folder / sanitize_filename(pseudonym)
        else:
            patient_folder = download_folder / sanitize_filename(patient_id)

        exclude_modalities = settings.EXCLUDE_MODALITIES
        modalities = study_modalities
        if pseudonym and exclude_modalities and study_modalities:
            included_modalities = [
                modality
                for modality in study_modalities.split(",")
                if modality not in exclude_modalities
            ]
            modalities = ",".join(included_modalities)
        prefix = f"{study_date}-{study_time}"
        study_folder = patient_folder / f"{prefix}-{modalities}"

        final_folder = study_folder
        if settings.CREATE_SERIES_SUB_FOLDERS:
            series_number = ds.get("SeriesNumber")
            if not series_number:
                series_folder_name = ds.SeriesInstanceUID
            else:
                series_description = ds.get("SeriesDescription", "Undefined")
                series_folder_name = f"{series_number}-{series_description}"
            series_folder_name = sanitize_filename(series_folder_name)
            final_folder = final_folder / series_folder_name

        file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
        file_path = str(final_folder / file_name)  # async_stream_zip expects a str

        dcm_buffer = BytesIO()
        write_dataset(ds, dcm_buffer)
        dcm_buffer.seek(0)

        return dcm_buffer, file_path

    async def single_buffer_gen(content):
        yield content

    async def async_queue_to_gen():
        try:
            while True:
                # Waits on the queue, when a queue item is retrieved,
                # we write it to an in-memory buffer and yield it
                queue_ds = await queue.get()
                if queue_ds is None:
                    break
                ds_buffer, file_path = await loop.run_in_executor(executor, ds_to_buffer, queue_ds)
                yield single_buffer_gen(ds_buffer.getvalue()), file_path
            # Re-raise any error caught during fetch_task
            if fetch_error:
                raise fetch_error
        # Because we cannot change the httpresponse once it has started streaming,
        # we add an error.txt file in the downloaded zip
        except Exception as err:
            err_buf = BytesIO(f"Error during study download:\n\n{err}".encode("utf-8"))
            yield single_buffer_gen(err_buf.getvalue()), "error.txt"
            raise

    async def generate_files_to_add_in_zip():
        modified_at = datetime.now()
        mode = S_IFREG | 0o600

        async for buffer_gen, file_path in async_queue_to_gen():
            yield (file_path, modified_at, mode, NO_COMPRESSION_64, buffer_gen)

    async def stream_zip() -> AsyncGenerator[bytes, None]:
        start_time = time.monotonic()
        try:
            async for zipped_file in async_stream_zip(generate_files_to_add_in_zip()):
                yield zipped_file
        finally:
            executor.shutdown(wait=True)
            elapsed = time.monotonic() - start_time
            logger.debug(f"Download completed in {elapsed:.2f} seconds")

    return StreamingHttpResponse(
        streaming_content=stream_zip(),
        headers={
            "Content-Type": "application/zip",
            "Content-Disposition": f'attachment; filename="{download_folder}.zip"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


class SelectiveTransferJobListView(SelectiveTransferLockedMixin, TransferJobListView):
    model = SelectiveTransferJob
    table_class = SelectiveTransferJobTable
    filterset_class = SelectiveTransferJobFilter
    template_name = "selective_transfer/selective_transfer_job_list.html"


class SelectiveTransferJobCreateView(SelectiveTransferLockedMixin, DicomJobCreateView):
    """A view class to render the selective transfer form.

    The form data itself is not processed by this view but by using WebSockets (see
    consumer.py). That way long running queries and cancellation can be used.
    """

    form_class = SelectiveTransferJobForm
    template_name = "selective_transfer/selective_transfer_job_form.html"
    permission_required = "selective_transfer.add_selectivetransferjob"
    request: AuthenticatedHttpRequest

    def post(self, request, *args, **kwargs):
        raise BadRequest("Form is only for use with WebSockets")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()

        preferences: dict[str, Any] = self.request.user.preferences
        kwargs["advanced_options_collapsed"] = preferences.get(
            SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED, False
        )

        return kwargs

    def get_initial(self):
        initial = super().get_initial()

        preferences: dict[str, Any] = self.request.user.preferences

        source = preferences.get(SELECTIVE_TRANSFER_SOURCE)
        if source is not None:
            initial["source"] = source

        destination = preferences.get(SELECTIVE_TRANSFER_DESTINATION)
        if destination is not None:
            initial["destination"] = destination

        urgent = preferences.get(SELECTIVE_TRANSFER_URGENT)
        if urgent is not None:
            initial["urgent"] = urgent

        send_finished_mail = preferences.get(SELECTIVE_TRANSFER_SEND_FINISHED_MAIL)
        if send_finished_mail is not None:
            initial["send_finished_mail"] = send_finished_mail

        return initial


class SelectiveTransferJobDetailView(SelectiveTransferLockedMixin, DicomJobDetailView):
    table_class = SelectiveTransferTaskTable
    filterset_class = SelectiveTransferTaskFilter
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"


class SelectiveTransferJobDeleteView(SelectiveTransferLockedMixin, DicomJobDeleteView):
    model = SelectiveTransferJob
    success_url = cast(str, reverse_lazy("selective_transfer_job_list"))


class SelectiveTransferJobVerifyView(SelectiveTransferLockedMixin, DicomJobVerifyView):
    model = SelectiveTransferJob


class SelectiveTransferJobCancelView(SelectiveTransferLockedMixin, DicomJobCancelView):
    model = SelectiveTransferJob


class SelectiveTransferJobResumeView(SelectiveTransferLockedMixin, DicomJobResumeView):
    model = SelectiveTransferJob


class SelectiveTransferJobRetryView(SelectiveTransferLockedMixin, DicomJobRetryView):
    model = SelectiveTransferJob


class SelectiveTransferJobRestartView(SelectiveTransferLockedMixin, DicomJobRestartView):
    model = SelectiveTransferJob


class SelectiveTransferTaskDetailView(SelectiveTransferLockedMixin, DicomTaskDetailView):
    model = SelectiveTransferTask
    job_url_name = "selective_transfer_job_detail"
    template_name = "selective_transfer/selective_transfer_task_detail.html"


class SelectiveTransferTaskDeleteView(SelectiveTransferLockedMixin, DicomTaskDeleteView):
    model = SelectiveTransferTask


class SelectiveTransferTaskResetView(SelectiveTransferLockedMixin, DicomTaskResetView):
    model = SelectiveTransferTask


class SelectiveTransferTaskKillView(SelectiveTransferLockedMixin, DicomTaskKillView):
    model = SelectiveTransferTask
