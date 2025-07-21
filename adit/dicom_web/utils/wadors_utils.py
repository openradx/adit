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

    For study-level requests, fetches each series individually to prevent
    loading the entire study into memory at once.
    """
    operator = DicomOperator(source_server)

    try:
        # For study-level requests, we need to fetch each series separately
        if level == "STUDY":
            # First, get the list of series in the study
            series_list = await sync_to_async(operator.find_series, thread_sensitive=False)(
                QueryDataset.create(
                    StudyInstanceUID=query["StudyInstanceUID"],
                )
            )

            # Process each series individually
            for series in series_list:
                series_query = {
                    "PatientID": query["PatientID"],
                    "StudyInstanceUID": query["StudyInstanceUID"],
                    "SeriesInstanceUID": series.SeriesInstanceUID,
                }

                # Fetch this individual series
                dicom_images = await fetch_dicom_data(source_server, series_query, "SERIES")

                # Convert to NIfTI and yield the files
                async for filename, file_content in process_single_fetch(dicom_images):
                    yield filename, file_content
        else:
            # For SERIES and IMAGE levels, process normally
            dicom_images = await fetch_dicom_data(source_server, query, level)
            async for filename, file_content in process_single_fetch(dicom_images):
                yield filename, file_content

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))


async def fetch_dicom_data(
    source_server: DicomServer,
    query: dict[str, str],
    level: Literal["STUDY", "SERIES", "IMAGE"],
) -> list[Dataset]:
    """Fetch DICOM data using WadoFetcher and return the list of datasets"""
    wado_fetcher = WadoFetcher(source_server, query)
    dicom_images: list[Dataset] = []

    def callback(ds: Dataset) -> None:
        dicom_images.append(ds)

    fetch_task = await wado_fetcher.create_fetch_task(level, callback)
    await WadoFetcher.execute_fetch(fetch_task)

    return dicom_images


async def process_single_fetch(dicom_images: list[Dataset]) -> AsyncIterator[tuple[str, BytesIO]]:
    """
    Process a list of DICOM datasets by converting them to NIfTI format
    and yield the resulting files. Only handles conversion and yielding,
    not the fetching of data.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write DICOM datasets to temporary files
        for file_idx, dicom_image in enumerate(dicom_images):
            dicom_file_path = temp_path / f"dicom_file_{file_idx}.dcm"
            write_dataset(dicom_image, dicom_file_path)

        # Convert the DICOM files to NIfTI
        nifti_output_dir = temp_path / "nifti_output"
        nifti_output_dir.mkdir(parents=True, exist_ok=True)
        converter = DicomToNiftiConverter()

        try:
            # Try to convert the DICOM files to NIfTI
            converter.convert(temp_path, nifti_output_dir)
        except Exception as e:
            # Log the error but continue execution
            logger.warning(f"Failed to convert some DICOM files to NIfTI: {str(e)}")
            # If the output directory is empty after a failed conversion, we won't yield any files

        # Collect all NIfTI and JSON files that were successfully created
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
