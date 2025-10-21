import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from io import BytesIO
from stat import S_IFREG
from typing import AsyncGenerator

from adit_radis_shared.accounts.models import User
from adrf.views import sync_to_async
from django.conf import settings
from pydicom import Dataset
from requests import HTTPError
from rest_framework.exceptions import NotFound
from stream_zip import NO_COMPRESSION_64, async_stream_zip

from adit.core.errors import DicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import construct_download_file_path, write_dataset

logger = logging.getLogger(__name__)


class DicomDownloader:
    def __init__(self, server_id):
        self.server_id = server_id
        self.manipulator = DicomManipulator()
        self.queue = asyncio.Queue[Dataset | None]()
        self.loop = asyncio.get_running_loop()

    async def download_study(
        self, user: User, patient_id, study_uid, study_params, download_folder
    ):
        """Directly downloads a study from a DicomServer"""

        download_errors: list[Exception] = []

        async with asyncio.TaskGroup() as tg:
            # Producer: Retrieves the study and puts Datasets in queue
            tg.create_task(
                self.retrieve_study(
                    user=user,
                    patient_id=patient_id,
                    study_uid=study_uid,
                    study_params=study_params,
                    download_errors=download_errors,
                )
            )
            try:
                # Consumer: Zips study Datasets from the async queue and yields them
                async for content in self.zip_study(
                    patient_id=patient_id,
                    study_params=study_params,
                    download_folder=download_folder,
                    download_errors=download_errors,
                ):
                    yield content
            except* Exception as eg:
                raise eg

    async def retrieve_study(
        self, user, patient_id, study_uid, study_params, download_errors: list[Exception]
    ):
        """Retrieves the study for download"""

        modifier = partial(
            self.manipulator.manipulate,
            pseudonym=study_params["pseudonym"],
            trial_protocol_id=study_params["trial_protocol_id"],
            trial_protocol_name=study_params["trial_protocol_name"],
        )
        fetch_put_task = asyncio.create_task(
            sync_to_async(self._fetch_put_study, thread_sensitive=False)(
                user=user,
                patient_id=patient_id,
                study_uid=study_uid,
                pseudonymize=bool(study_params["pseudonym"]),
                modifier=modifier,
            )
        )
        asyncio.create_task(self._put_sentinel(fetch_put_task, download_errors))

    def _fetch_put_study(self, user, patient_id, study_uid, pseudonymize, modifier):
        """Fetches Datasets of a study and puts them into the async queue"""

        def callback(ds: Dataset) -> None:
            modifier(ds)
            # Schedules a task on the event loop that puts the dataset into the async queue
            self.loop.call_soon_threadsafe(self.queue.put_nowait, ds)

        try:
            server = DicomServer.objects.accessible_by_user(user, "source").get(id=self.server_id)
            operator = DicomOperator(server)

            exclude_modalities = settings.EXCLUDE_MODALITIES

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
        # Re-raise DicomErrors/HttpErrors from fetch_series/fetch_study
        except (DicomError, HTTPError):
            raise

    async def _put_sentinel(self, fetch_put_task, download_errors):
        """Inserts sentinel to the queue at the end of fetch_put_task"""
        try:
            await fetch_put_task
        # Re-raise the errors raised by _fetch_put_study
        except Exception as err:
            download_errors.append(err)
        finally:
            await self.queue.put(None)

    async def zip_study(
        self, patient_id, study_params, download_folder, download_errors
    ) -> AsyncGenerator[bytes, None]:
        """Stream zips the retrieved study in the async queue"""

        async def generate_files_to_add_in_zip(executor: ThreadPoolExecutor):
            modified_at = datetime.now()
            mode = S_IFREG | 0o600

            async for buffer_gen, file_path in self._consume_queue(
                executor, patient_id, study_params, download_folder, download_errors
            ):
                yield (file_path, modified_at, mode, NO_COMPRESSION_64, buffer_gen)

        start_time = time.monotonic()
        executor = ThreadPoolExecutor()
        try:
            async for zipped_file in async_stream_zip(generate_files_to_add_in_zip(executor)):
                yield zipped_file
        finally:
            executor.shutdown(wait=True)
            elapsed = time.monotonic() - start_time
            logger.debug(f"Download completed in {elapsed:.2f} seconds")

    async def _consume_queue(
        self, executor, patient_id, study_params, download_folder, download_errors
    ):
        """Consumes and yields the datasets from the async queue"""

        def ds_to_buffer(ds):
            """Writes the dataset to a buffer and constructs the corresponding file path"""
            ds_buffer = BytesIO()
            write_dataset(ds, ds_buffer)
            ds_buffer.seek(0)

            file_path = construct_download_file_path(
                ds,
                download_folder,
                patient_id,
                study_params["study_modalities"],
                study_params["study_date"],
                study_params["study_time"],
                study_params["pseudonym"],
            )

            return ds_buffer, str(file_path)

        async def buffer_to_gen(content):
            """Wraps dataset buffer in an async generator, expected by async_stream_zip"""
            yield content

        while True:
            # Waits on the queue, when a queue item is retrieved,
            # we write it to an in-memory buffer and yield it
            queue_ds = await self.queue.get()
            if queue_ds is None:
                break
            ds_buffer, file_path = await self.loop.run_in_executor(executor, ds_to_buffer, queue_ds)
            yield buffer_to_gen(ds_buffer.getvalue()), file_path
        # Re-raise any error caught during _fetch_put_study
        if download_errors:
            # Because we cannot change the httpresponse once it has started streaming,
            # we add an error.txt file in the downloaded zip
            err_buf = BytesIO(f"Error during study download:\n\n{err}".encode("utf-8"))
            yield buffer_to_gen(err_buf.getvalue()), "error.txt"
