import asyncio
import logging
import os
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator, Literal

import aiofiles
import aiofiles.os
from adrf.views import sync_to_async
from aiofiles.tempfile import TemporaryDirectory
from pydicom import Dataset

from adit.core.errors import (
    DcmToNiftiConversionError,
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

logger = logging.getLogger(__name__)

# Modalities that are known to not contain image data and cannot be converted to NIfTI.
# SR = Structured Reports, KO = Key Object Selection, PR = Presentation State.
NON_IMAGE_MODALITIES = {"SR", "KO", "PR"}


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
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Dataset | None] = asyncio.Queue()

    dicom_manipulator = DicomManipulator()

    def callback(ds: Dataset) -> None:
        dicom_manipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)
        loop.call_soon_threadsafe(queue.put_nowait, ds)

    def fetch_with_sentinel(fetch_func: Callable[..., None], **kwargs: object) -> None:
        """Wrapper that calls fetch function and schedules sentinel afterward.

        By scheduling the sentinel via call_soon_threadsafe from within the same
        thread (after the sync function completes), we guarantee FIFO ordering:
        all data callbacks scheduled during fetch will be processed before the
        sentinel because they were scheduled first.
        """
        try:
            fetch_func(**kwargs)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    try:
        if level == "STUDY":
            fetch_coro = sync_to_async(fetch_with_sentinel, thread_sensitive=False)(
                operator.fetch_study,
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                callback=callback,
            )
        elif level == "SERIES":
            fetch_coro = sync_to_async(fetch_with_sentinel, thread_sensitive=False)(
                operator.fetch_series,
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                series_uid=query_ds.SeriesInstanceUID,
                callback=callback,
            )
        elif level == "IMAGE":
            assert query_ds.has("SeriesInstanceUID")
            fetch_coro = sync_to_async(fetch_with_sentinel, thread_sensitive=False)(
                operator.fetch_image,
                patient_id=query_ds.PatientID,
                study_uid=query_ds.StudyInstanceUID,
                series_uid=query_ds.SeriesInstanceUID,
                image_uid=query_ds.SOPInstanceUID,
                callback=callback,
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")

        # Start fetch task. Sentinel will be added via call_soon_threadsafe when done.
        fetch_task = asyncio.create_task(fetch_coro)

        try:
            while True:
                queue_ds = await queue.get()
                if queue_ds is None:
                    break
                yield queue_ds
        finally:
            # Ensure fetch task is properly awaited even if consumer stops early
            if not fetch_task.done():
                fetch_task.cancel()
            try:
                await fetch_task
            except asyncio.CancelledError:
                pass

    except RetriableDicomError as exc:
        raise ServiceUnavailableApiError(str(exc))
    except DicomError as exc:
        raise BadGatewayApiError(str(exc))


def _fetch_dicom_data(
    source_server: DicomServer,
    query: dict[str, str],
    level: Literal["STUDY", "SERIES", "IMAGE"],
) -> list[Dataset]:
    """Fetch DICOM data synchronously and return the list of datasets."""
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)
    dicom_images: list[Dataset] = []

    def callback(ds: Dataset) -> None:
        dicom_images.append(ds)

    if level == "STUDY":
        operator.fetch_study(
            patient_id=query_ds.PatientID,
            study_uid=query_ds.StudyInstanceUID,
            callback=callback,
        )
    elif level == "SERIES":
        operator.fetch_series(
            patient_id=query_ds.PatientID,
            study_uid=query_ds.StudyInstanceUID,
            series_uid=query_ds.SeriesInstanceUID,
            callback=callback,
        )
    elif level == "IMAGE":
        assert query_ds.has("SeriesInstanceUID")
        operator.fetch_image(
            patient_id=query_ds.PatientID,
            study_uid=query_ds.StudyInstanceUID,
            series_uid=query_ds.SeriesInstanceUID,
            image_uid=query_ds.SOPInstanceUID,
            callback=callback,
        )
    else:
        raise ValueError(f"Invalid WADO-RS level: {level}.")

    return dicom_images


async def wado_retrieve_nifti(
    source_server: DicomServer,
    query: dict[str, str],
    level: Literal["STUDY", "SERIES", "IMAGE"],
) -> AsyncIterator[tuple[str, BytesIO]]:
    """Retrieve DICOM data and convert to NIfTI format.

    Returns the generated files (NIfTI, JSON, bval, bvec) as tuples of
    (filename, file_content).

    For study-level requests, fetches each series individually to prevent
    loading the entire study into memory at once. Non-image series (SR, KO, PR)
    are skipped before fetching.
    """
    operator = DicomOperator(source_server)

    try:
        if level == "STUDY":
            series_list = await sync_to_async(operator.find_series, thread_sensitive=False)(
                QueryDataset.create(
                    StudyInstanceUID=query["StudyInstanceUID"],
                )
            )

            for series in series_list:
                modality = series.Modality
                if modality in NON_IMAGE_MODALITIES:
                    logger.debug(
                        f"Skipping non-image series {series.SeriesInstanceUID} "
                        f"(modality: {modality})"
                    )
                    continue

                series_query = {
                    "PatientID": query["PatientID"],
                    "StudyInstanceUID": query["StudyInstanceUID"],
                    "SeriesInstanceUID": series.SeriesInstanceUID,
                }

                dicom_images = await sync_to_async(_fetch_dicom_data, thread_sensitive=False)(
                    source_server, series_query, "SERIES"
                )

                async for filename, file_content in _process_single_fetch(dicom_images):
                    yield filename, file_content
        else:
            dicom_images = await sync_to_async(_fetch_dicom_data, thread_sensitive=False)(
                source_server, query, level
            )
            async for filename, file_content in _process_single_fetch(dicom_images):
                yield filename, file_content

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))


async def _process_single_fetch(
    dicom_images: list[Dataset],
) -> AsyncIterator[tuple[str, BytesIO]]:
    """Convert a list of DICOM datasets to NIfTI format and yield the resulting files.

    For each conversion output group (identified by base filename), yields files in order:
    JSON sidecar first, then NIfTI (.nii.gz or .nii), then bval, then bvec.

    If conversion fails with NoValidDicomError or NoSpatialDataError, a warning is logged
    because the series was expected to contain image data (non-image modalities are filtered
    out before this function is called).
    """
    async with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for file_idx, dicom_image in enumerate(dicom_images):
            dicom_file_path = temp_path / f"dicom_file_{file_idx}.dcm"
            await sync_to_async(write_dataset, thread_sensitive=False)(dicom_image, dicom_file_path)

        nifti_output_dir = temp_path / "nifti_output"
        await aiofiles.os.makedirs(nifti_output_dir, exist_ok=True)
        converter = DicomToNiftiConverter()

        try:
            await sync_to_async(converter.convert, thread_sensitive=False)(
                temp_path, nifti_output_dir
            )
        except (NoValidDicomError, NoSpatialDataError) as e:
            # The series passed the modality check but still failed conversion.
            # This is unexpected and worth logging as a warning.
            logger.warning(f"Series conversion failed unexpectedly: {e}")
            return
        except DcmToNiftiConversionError as e:
            logger.warning(f"Failed to convert DICOM files to NIfTI: {e}")
            return
        except Exception as e:
            logger.error(f"Error during DICOM to NIfTI conversion: {e}")
            raise

        entries = await aiofiles.os.scandir(nifti_output_dir)
        all_files = [entry.name for entry in entries]

        file_pairs: dict[str, dict[str, str]] = {}
        for filename in all_files:
            base_name, ext = os.path.splitext(filename)
            if ext == ".json":
                file_pairs.setdefault(base_name, {})["json"] = filename
            elif ext == ".gz" and base_name.endswith(".nii"):
                actual_base = os.path.splitext(base_name)[0]
                file_pairs.setdefault(actual_base, {})["nifti"] = filename
            elif ext == ".nii":
                file_pairs.setdefault(base_name, {})["nifti"] = filename
            elif ext == ".bval":
                file_pairs.setdefault(base_name, {})["bval"] = filename
            elif ext == ".bvec":
                file_pairs.setdefault(base_name, {})["bvec"] = filename

        file_order = ["json", "nifti", "bval", "bvec"]
        for _base_name, files in file_pairs.items():
            for file_type in file_order:
                if file_type in files:
                    file_path = os.path.join(nifti_output_dir, files[file_type])
                    async with aiofiles.open(file_path, "rb") as f:
                        content = await f.read()
                        yield files[file_type], BytesIO(content)
