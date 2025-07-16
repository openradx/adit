import asyncio
import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator, Callable, Literal

from adrf.views import sync_to_async
from pydicom import Dataset

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_to_nifti_converter import DicomToNiftiConverter
from adit.core.utils.dicom_utils import write_dataset

from ..errors import BadGatewayApiError, ServiceUnavailableApiError

logger = logging.getLogger("__name__")


class WadoFetcher:
    """Helper class for WADO fetch operations to avoid code duplication."""

    def __init__(self, source_server: DicomServer, query: dict[str, str]):
        self.source_server = source_server
        self.query_ds = QueryDataset.from_dict(query)
        self.operator = DicomOperator(source_server)

    async def create_fetch_task(
        self, level: Literal["STUDY", "SERIES", "IMAGE"], callback: Callable[[Dataset], None]
    ) -> asyncio.Task:
        """Create and return a fetch task based on the level."""
        if level == "STUDY":
            return asyncio.create_task(
                sync_to_async(self.operator.fetch_study, thread_sensitive=False)(
                    patient_id=self.query_ds.PatientID,
                    study_uid=self.query_ds.StudyInstanceUID,
                    callback=callback,
                )
            )
        elif level == "SERIES":
            return asyncio.create_task(
                sync_to_async(self.operator.fetch_series, thread_sensitive=False)(
                    patient_id=self.query_ds.PatientID,
                    study_uid=self.query_ds.StudyInstanceUID,
                    series_uid=self.query_ds.SeriesInstanceUID,
                    callback=callback,
                )
            )
        elif level == "IMAGE":
            assert self.query_ds.has("SeriesInstanceUID")
            return asyncio.create_task(
                sync_to_async(self.operator.fetch_image, thread_sensitive=False)(
                    patient_id=self.query_ds.PatientID,
                    study_uid=self.query_ds.StudyInstanceUID,
                    series_uid=self.query_ds.SeriesInstanceUID,
                    image_uid=self.query_ds.SOPInstanceUID,
                    callback=callback,
                )
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")

    @staticmethod
    async def execute_fetch(fetch_task: asyncio.Task) -> None:
        """Execute the fetch task and handle common errors."""
        try:
            await asyncio.wait([fetch_task])
        except RetriableDicomError as err:
            raise ServiceUnavailableApiError(str(err))
        except DicomError as err:
            raise BadGatewayApiError(str(err))


async def wado_retrieve(
    source_server: DicomServer,
    query: dict[str, str],
    level: Literal["STUDY", "SERIES", "IMAGE"],
    pseudonym: str | None = None,
    trial_protocol_id: str | None = None,
    trial_protocol_name: str | None = None,
) -> AsyncIterator[Dataset]:
    """WADO retrieve helper.

    Mainly converts a sync callback (by the operator) to an async iterator.
    """
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue[Dataset]()
    dicom_manipulator = DicomManipulator()
    wado_fetcher = WadoFetcher(source_server, query)

    def callback(ds: Dataset) -> None:
        dicom_manipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)
        loop.call_soon_threadsafe(queue.put_nowait, ds)

    try:
        fetch_task = await wado_fetcher.create_fetch_task(level, callback)

        while True:
            queue_get_task = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                [fetch_task, queue_get_task], return_when=asyncio.FIRST_COMPLETED
            )

            finished = False
            for task in done:
                if task == queue_get_task:
                    yield queue_get_task.result()
                if task == fetch_task:
                    finished = True

            if finished:
                queue_get_task.cancel()
                break

        await asyncio.wait([fetch_task, queue_get_task])

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))


async def wado_retrieve_nifti(
    source_server: DicomServer,
    query: dict[str, str],
    level: Literal["STUDY", "SERIES", "IMAGE"],
) -> AsyncIterator[tuple[str, BytesIO]]:
    """
    Returns the generated files (NIfTI and JSON) as tuples in the format
    (filename, file content).
    """
    dicom_images: list[Dataset] = []
    wado_fetcher = WadoFetcher(source_server, query)

    def callback(ds: Dataset) -> None:
        dicom_images.append(ds)

    try:
        fetch_task = await wado_fetcher.create_fetch_task(level, callback)
        await WadoFetcher.execute_fetch(fetch_task)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_idx = 0

            # Write DICOM datasets to temporary files
            for dicom_image in dicom_images:
                dicom_file_path = temp_path / f"dicom_file_{file_idx}.dcm"
                write_dataset(dicom_image, dicom_file_path)
                file_idx += 1

            # Convert the DICOM files to NIfTI
            nifti_output_dir = temp_path / "nifti_output"
            nifti_output_dir.mkdir(parents=True, exist_ok=True)
            converter = DicomToNiftiConverter()
            converter.convert(temp_path, nifti_output_dir)

            # Collect all NIfTI and JSON files
            nifti_files = list(nifti_output_dir.glob("*.nii*"))
            json_files = list(nifti_output_dir.glob("*.json"))

            # First yield all the NIfTI files
            for nifti_file in nifti_files:
                nifti_filename = nifti_file.name
                with open(nifti_file, "rb") as f:
                    nifti_content = f.read()
                    yield nifti_filename, BytesIO(nifti_content)

            # Then yield all the JSON files
            for json_file in json_files:
                json_filename = json_file.name
                with open(json_file, "rb") as f:
                    json_content = f.read()
                    yield json_filename, BytesIO(json_content)

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))
