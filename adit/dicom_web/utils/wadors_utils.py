import asyncio
import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator, Literal

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
    queue = asyncio.Queue[Dataset]()

    dicom_manipulator = DicomManipulator()

    def callback(ds: Dataset) -> None:
        dicom_manipulator.manipulate(ds, pseudonym, trial_protocol_id, trial_protocol_name)

        loop.call_soon_threadsafe(queue.put_nowait, ds)

    try:
        if level == "STUDY":
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_study, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    callback=callback,
                )
            )
        elif level == "SERIES":
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_series, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    series_uid=query_ds.SeriesInstanceUID,
                    callback=callback,
                )
            )
        elif level == "IMAGE":
            assert query_ds.has("SeriesInstanceUID")
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_image, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    series_uid=query_ds.SeriesInstanceUID,
                    image_uid=query_ds.SOPInstanceUID,
                    callback=callback,
                )
            )
        else:
            raise ValueError(f"Invalid WADO-RS level: {level}.")

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
    operator = DicomOperator(source_server)
    query_ds = QueryDataset.from_dict(query)
    dicom_images: list[Dataset] = []

    def callback(ds: Dataset) -> None:
        dicom_images.append(ds)

    try:
        if level == "SERIES":
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_series, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    series_uid=query_ds.SeriesInstanceUID,
                    callback=callback,
                )
            )
        elif level == "STUDY":
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_study, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    callback=callback,
                )
            )
        elif level == "IMAGE":
            assert query_ds.has("SeriesInstanceUID")
            fetch_task = asyncio.create_task(
                sync_to_async(operator.fetch_image, thread_sensitive=False)(
                    patient_id=query_ds.PatientID,
                    study_uid=query_ds.StudyInstanceUID,
                    series_uid=query_ds.SeriesInstanceUID,
                    image_uid=query_ds.SOPInstanceUID,
                    callback=callback,
                )
            )
        else:
            raise ValueError(f"Invalid NIFTI-WADO-RS level: {level}.")

        await asyncio.wait([fetch_task])

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

            # Yield each NIfTI and JSON file with their filenames
            for nifti_file in nifti_output_dir.glob("*.nii*"):
                nifti_filename = nifti_file.name
                json_filename = nifti_file.with_suffix(".json").name

                # Read and yield the NIfTI file
                with open(nifti_file, "rb") as f:
                    nifti_content = f.read()
                    yield nifti_filename, BytesIO(nifti_content)

                # Read and yield the JSON file
                json_file = nifti_file.with_suffix(".json")
                if json_file.exists():
                    with open(json_file, "rb") as f:
                        json_content = f.read()
                        yield json_filename, BytesIO(json_content)

    except RetriableDicomError as err:
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        raise BadGatewayApiError(str(err))
