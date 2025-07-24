import asyncio
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator, Callable, Literal

import aiofiles
import aiofiles.os
from adrf.views import sync_to_async
from aiofiles.tempfile import TemporaryDirectory
from pydicom import Dataset

from adit.core.errors import (
    DicomConversionError,
    DicomError,
    NoSpatialDataError,
    NoValidDicomError,
    RetriableDicomError,
)
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

    def create_fetch_task(
        self, level: Literal["STUDY", "SERIES", "IMAGE"], callback: Callable[[Dataset], None]
    ):
        """Create and return a sync_to_async coroutine based on the level.

        The caller is responsible for wrapping this in asyncio.create_task() if needed.
        """
        if level == "STUDY":
            return sync_to_async(self.operator.fetch_study, thread_sensitive=False)(
                patient_id=self.query_ds.PatientID,
                study_uid=self.query_ds.StudyInstanceUID,
                callback=callback,
            )
        elif level == "SERIES":
            return sync_to_async(self.operator.fetch_series, thread_sensitive=False)(
                patient_id=self.query_ds.PatientID,
                study_uid=self.query_ds.StudyInstanceUID,
                series_uid=self.query_ds.SeriesInstanceUID,
                callback=callback,
            )
        elif level == "IMAGE":
            assert self.query_ds.has("SeriesInstanceUID")
            return sync_to_async(self.operator.fetch_image, thread_sensitive=False)(
                patient_id=self.query_ds.PatientID,
                study_uid=self.query_ds.StudyInstanceUID,
                series_uid=self.query_ds.SeriesInstanceUID,
                image_uid=self.query_ds.SOPInstanceUID,
                callback=callback,
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")


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
        fetch_task = asyncio.create_task(wado_fetcher.create_fetch_task(level, callback))

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

    try:
        await wado_fetcher.create_fetch_task(level, callback)

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))

    return dicom_images


async def process_single_fetch(dicom_images: list[Dataset]) -> AsyncIterator[tuple[str, BytesIO]]:
    """
    Process a list of DICOM datasets by converting them to NIfTI format
    and yield the resulting files. Only handles conversion and yielding,
    not the fetching of data.

    For each file pair, yields the JSON file first, then the corresponding NIfTI file.

    Expected exceptions like NoValidDicomError and NoSpatialDataError are handled
    silently as these indicate series that simply cannot be converted to NIfTI,
    rather than actual errors.
    """
    async with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write DICOM datasets to temporary files
        for file_idx, dicom_image in enumerate(dicom_images):
            dicom_file_path = temp_path / f"dicom_file_{file_idx}.dcm"
            # Use sync_to_async to make write_dataset non-blocking
            await sync_to_async(write_dataset, thread_sensitive=False)(dicom_image, dicom_file_path)

        # Convert the DICOM files to NIfTI
        nifti_output_dir = temp_path / "nifti_output"
        await aiofiles.os.makedirs(nifti_output_dir, exist_ok=True)
        converter = DicomToNiftiConverter()

        try:
            # Use sync_to_async for the converter
            await sync_to_async(converter.convert, thread_sensitive=False)(
                temp_path, nifti_output_dir
            )
        except (NoValidDicomError, NoSpatialDataError):
            # These exceptions are expected for series that cannot be converted to NIfTI
            # For example, non-image series (e.g., SR documents) or series without spatial data
            # No warning needed, just skip this series without yielding any files
            return
        except DicomConversionError as e:
            # Log warning for conversion errors that aren't critical but worth noting
            logger.warning(f"Failed to convert DICOM files to NIfTI: {str(e)}")
            # For conversion errors, there won't be any output files to process
            return
        except Exception as e:
            # For serious errors (disk full, permissions, etc.), log and propagate the error
            logger.error(f"Error during DICOM to NIfTI conversion: {str(e)}")
            # Raise the original exception to properly propagate serious errors
            raise e

        # Get all files in the output directory using aiofiles instead of sync_to_async(os.listdir)
        entries = await aiofiles.os.scandir(nifti_output_dir)
        all_files = [entry.name for entry in entries]

        # Create a mapping of base filenames to their corresponding file paths
        file_pairs = {}
        for filename in all_files:
            base_name, ext = os.path.splitext(filename)
            if ext == ".json":
                # For JSON files, store directly
                file_pairs.setdefault(base_name, {}).update({"json": filename})
            elif ext == ".gz" and base_name.endswith(".nii"):
                # For .nii.gz files, strip the .nii part from the base_name
                actual_base = os.path.splitext(base_name)[0]
                file_pairs.setdefault(actual_base, {}).update({"nifti": filename})
            elif ext == ".nii":
                # For .nii files
                file_pairs.setdefault(base_name, {}).update({"nifti": filename})
            elif ext == ".bval":
                # For .bval files (diffusion b-values)
                file_pairs.setdefault(base_name, {}).update({"bval": filename})
            elif ext == ".bvec":
                # For .bvec files (diffusion b-vectors)
                file_pairs.setdefault(base_name, {}).update({"bvec": filename})

        # Yield file pairs, JSON first then NIfTI, and finally bval/bvec if they exist
        for base_name, files in file_pairs.items():
            # First yield the JSON file if it exists
            if "json" in files:
                json_filename = files["json"]
                json_file_path = os.path.join(nifti_output_dir, json_filename)
                async with aiofiles.open(json_file_path, "rb") as f:
                    json_content = await f.read()
                    yield json_filename, BytesIO(json_content)

            # Then yield the NIfTI file if it exists
            if "nifti" in files:
                nifti_filename = files["nifti"]
                nifti_file_path = os.path.join(nifti_output_dir, nifti_filename)
                async with aiofiles.open(nifti_file_path, "rb") as f:
                    nifti_content = await f.read()
                    yield nifti_filename, BytesIO(nifti_content)

            # Then yield the bval file if it exists (diffusion b-values)
            if "bval" in files:
                bval_filename = files["bval"]
                bval_file_path = os.path.join(nifti_output_dir, bval_filename)
                async with aiofiles.open(bval_file_path, "rb") as f:
                    bval_content = await f.read()
                    yield bval_filename, BytesIO(bval_content)

            # Finally yield the bvec file if it exists (diffusion b-vectors)
            if "bvec" in files:
                bvec_filename = files["bvec"]
                bvec_file_path = os.path.join(nifti_output_dir, bvec_filename)
                async with aiofiles.open(bvec_file_path, "rb") as f:
                    bvec_content = await f.read()
                    yield bvec_filename, BytesIO(bvec_content)
