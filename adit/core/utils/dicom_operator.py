"""The operator is a high level abstraction to communicate with PACS servers.

Under the hood it uses the DIMSE and DICOMweb connector classes for communication with
the server.

Some PACS servers (like our Synapse) don't support filtering the queries by each attribute so
we do this additionally in a programmatic way. For example the PatientBirthDate as it is optional
in the Patient Root Query/Retrieve Information Model
(see https://groups.google.com/g/comp.protocols.dicom/c/h28r_znomEw).
"""

import asyncio
import errno
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from os import PathLike
from pathlib import Path
from typing import Callable, Iterable, Iterator

from aiofiles import os as async_os
from django.conf import settings
from pydicom import Dataset
from pynetdicom.events import Event

from ..errors import DicomCommunicationError, OutOfDiskSpaceError
from ..models import DicomServer
from .dicom_dataset import QueryDataset, ResultDataset
from .dicom_utils import (
    convert_to_python_regex,
    has_wildcards,
    read_dataset,
    write_dataset,
)
from .dicom_web_connector import DicomWebConnector
from .dimse_connector import DimseConnector
from .file_transmit import FileTransmitClient, Metadata
from .sanitize import sanitize_dirname

logger = logging.getLogger(__name__)

Modifier = Callable[[Dataset], None]


class DicomOperator:
    def __init__(
        self,
        server: DicomServer,
        connection_retries: int = 2,
        timeout: int | None = None,
    ):
        self.server = server
        self.dimse_connector = DimseConnector(
            server,
            connection_retries=connection_retries,
            acse_timeout=timeout,
            dimse_timeout=timeout,
            network_timeout=timeout,
        )
        # TODO: also make retries and timeouts possible in DicomWebConnector
        self.dicom_web_connector = DicomWebConnector(server)

    def abort(self) -> None:
        self.dimse_connector.abort_connection()
        self.dicom_web_connector.abort()

    def find_patients(
        self,
        query: QueryDataset,
        limit_results: int | None = None,
    ) -> Iterator[ResultDataset]:
        """Find patients for given query and return a list of patient datasets.

        For patient level patient root C-FIND query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part04.html#table_C.6-1

        If patient root level queries are not supported by the server then we do a study root query
        and filter the patients programmatically.
        For study level study root C-FIND query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part04.html#table_C.6-5

        In DICOMweb QIDO-RS there is also no patient level query, so we also do a study level query
        and filter the patients programmatically.
        For study level DICOMweb QIDO-RS query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.1-5
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.3-3
        """
        query.ensure_elements(
            "PatientID",
            "PatientName",
            "PatientBirthDate",
            "PatientSex",
            "NumberOfPatientRelatedStudies",
        )

        if self.server.patient_root_find_support or self.server.study_root_find_support:
            if self.server.patient_root_find_support:
                query.QueryRetrieveLevel = "PATIENT"
            else:
                # If no patient root is supported we have to emulate the query on study root
                query.QueryRetrieveLevel = "STUDY"

            results = self.dimse_connector.send_c_find(query, limit_results=limit_results)
            yield from self._handle_found_patients(query, results)

        elif self.server.dicomweb_qido_support:
            query.QueryRetrieveLevel = "STUDY"

            results = self.dicom_web_connector.send_qido_rs(query, limit_results=limit_results)
            yield from self._handle_found_patients(query, results)

        else:
            raise ValueError("No supported method to find patients.")

    def _handle_found_patients(
        self, query: QueryDataset, results: Iterable[ResultDataset]
    ) -> Iterator[ResultDataset]:
        # When querying on study level we have to make patients unique since it then
        # returns all studies for one patient, resulting in duplicate patients
        seen: set[str] = set()

        for result in results:
            if result.PatientID in seen:
                continue
            seen.add(result.PatientID)

            # Currently we don't allow a range filter for PatientBirthDate
            if query.has("PatientBirthDate"):
                if query.PatientBirthDate != result.PatientBirthDate:
                    continue

            if query.has("PatientName"):
                patient_name_pattern = convert_to_python_regex(query.PatientName)
                if not patient_name_pattern.search(result.PatientName):
                    continue

            if query.has("PatientSex"):
                if query.PatientSex != result.PatientSex:
                    continue

            yield result

    def find_studies(
        self,
        query: QueryDataset,
        limit_results: int | None = None,
    ) -> Iterator[ResultDataset]:
        """Find studies for given query and return a list of study datasets.

        For study level patient root query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part04.html#table_C.6-2

        For study level study root query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part04.html#table_C.6-5

        For study level DICOMweb QIDO-RS query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.1-5
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.3-3
        """
        query.ensure_elements(
            "PatientID",
            "PatientName",
            "PatientBirthDate",
            "StudyInstanceUID",
            "AccessionNumber",
            "StudyDate",
            "StudyTime",
            "StudyDescription",
            "ModalitiesInStudy",
            "NumberOfStudyRelatedSeries",
            "NumberOfStudyRelatedInstances",
        )

        query.QueryRetrieveLevel = "STUDY"

        if self.server.patient_root_find_support or self.server.study_root_find_support:
            results = self.dimse_connector.send_c_find(query, limit_results=limit_results)
            yield from self._handle_found_studies(query, results)
        elif self.server.dicomweb_qido_support:
            results = self.dicom_web_connector.send_qido_rs(query, limit_results=limit_results)
            yield from self._handle_found_studies(query, results)
        else:
            raise ValueError("No supported method to find studies.")

    def _handle_found_studies(
        self,
        query: QueryDataset,
        results: Iterable[ResultDataset],
    ) -> Iterator[ResultDataset]:
        for result in results:
            # Optionally filter by its study description, if the server doesn't support it
            if query.has("StudyDescription"):
                study_description_pattern = convert_to_python_regex(query.StudyDescription)
                if not study_description_pattern.search(result.StudyDescription):
                    continue

            # TODO: I guess this won't work as we are in the middle of a C-FIND request (we
            # are using generators now) and we can't do another C-FIND request here.
            # But we could use a new Connector instance for this. Fix this later.
            # if "ModalitiesInStudy" not in result:
            #     result.ModalitiesInStudy = self._fetch_study_modalities(
            #         result.PatientID, result.StudyInstanceUID
            #     )

            if query.has("ModalitiesInStudy"):
                modalities = result.ModalitiesInStudy
                # It's ok if any of the searched modalities is in this study
                if not any(modality in modalities for modality in query.ModalitiesInStudy):
                    continue

            yield result

    def _fetch_study_modalities(self, patient_id: str, study_uid: str) -> list[str]:
        series_list = list(
            self.find_series(
                QueryDataset.create(
                    PatientID=patient_id,
                    StudyInstanceUID=study_uid,
                )
            )
        )
        modalities = set()
        for series in series_list:
            modalities.add(series.Modality)
        return sorted(list(modalities))

    def find_series(
        self,
        query: QueryDataset,
        limit_results=None,
    ) -> Iterator[ResultDataset]:
        """Find series for given query and return a list of series datasets.

        For series level patient root query and study root query support the same attributes:
        https://dicom.nema.org/medical/dicom/current/output/html/part04.html#table_C.6-3

        For series level DICOMweb QIDO-RS query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.1-5
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.3-4
        """
        query.ensure_elements(
            "PatientID",
            "StudyInstanceUID",
            "SeriesInstanceUID",
            "SeriesDescription",
            "SeriesNumber",
            "Modality",
            "NumberOfSeriesRelatedInstances",
        )

        # A StudyInstanceUID is always required for querying series, regardless of C-FIND or QIDO-RS
        study_uid = query.get("StudyInstanceUID")
        if not study_uid or has_wildcards(study_uid):
            raise ValueError("StudyInstanceUID is required for querying series.")

        query.QueryRetrieveLevel = "SERIES"

        if self.server.patient_root_find_support or self.server.study_root_find_support:
            if not self.server.study_root_find_support:
                patient_id = query.get("PatientID")
                if not patient_id or has_wildcards(patient_id):
                    raise ValueError(
                        "PatientID is required for querying series with "
                        "Patient Root Query/Retrieve Information Model."
                    )

            results = self.dimse_connector.send_c_find(query, limit_results=limit_results)
            yield from self._handle_found_series(query, results)
        else:
            results = self.dicom_web_connector.send_qido_rs(query, limit_results=limit_results)
            yield from self._handle_found_series(query, results)

    def _handle_found_series(
        self,
        query: QueryDataset,
        results: Iterable[ResultDataset],
    ) -> Iterator[ResultDataset]:
        for result in results:
            # It's also better to filter Series Number programmatically, because it's of
            # VR Integer String and with just a C-Find it's not guaranteed that e.g.
            # "4" is the same as "+4"
            # https://groups.google.com/g/comp.protocols.dicom/c/JNsg7upVJ08
            if query.has("SeriesNumber"):
                series_number_query = query.SeriesNumber
                if series_number_query != result.SeriesNumber:
                    continue

            # Optionally filter by modality, if the server doesn't support it
            if query.has("Modality"):
                if query.Modality != result.Modality:
                    continue

            # Optionally filter by series description, if the server doesn't support it
            if query.has("SeriesDescription"):
                series_description_pattern = convert_to_python_regex(query.SeriesDescription)
                if not series_description_pattern.search(result.SeriesDescription):
                    continue

            yield result

    def find_images(
        self, query: QueryDataset, limit_results: int | None = None
    ) -> Iterator[ResultDataset]:
        """Find images for given query and return a list of image datasets.

        For image level patient root query and study root query support the same attributes:
        https://dicom.nema.org/medical/dicom/current/output/html/part04.html#table_C.6-4

        For image level DICOMweb QIDO-RS query see:
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.1-5
        https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.3-5
        """
        query.ensure_elements(
            "PatientID",
            "StudyInstanceUID",
            "SeriesInstanceUID",
            "SOPInstanceUID",
            "InstanceNumber",
            "InstanceAvailability",
        )

        # A StudyInstanceUID and SeriesInstanceUID is always required for querying images,
        # regardless of C-FIND or QIDO-RS
        study_uid = query.get("StudyInstanceUID")
        if not study_uid or has_wildcards(study_uid):
            raise ValueError("StudyInstanceUID is required for querying images.")
        series_uid = query.get("SeriesInstanceUID")
        if not series_uid or has_wildcards(series_uid):
            raise ValueError("SeriesInstanceUID is required for querying images.")

        query.QueryRetrieveLevel = "IMAGE"

        if self.server.patient_root_find_support or self.server.study_root_find_support:
            if not self.server.study_root_find_support:
                patient_id = query.get("PatientID")
                if not patient_id or has_wildcards(patient_id):
                    raise ValueError(
                        "PatientID is required for querying images with "
                        "Patient Root Query/Retrieve Information Model."
                    )

            yield from self.dimse_connector.send_c_find(query, limit_results=limit_results)
        elif self.server.dicomweb_qido_support:
            yield from self.dicom_web_connector.send_qido_rs(query, limit_results=limit_results)
        else:
            raise ValueError("No supported method to find images.")

    def download_study(
        self,
        patient_id: str,
        study_uid: str,
        dest_folder: PathLike,
        modality: str = "",
        modifier: Modifier | None = None,
    ):
        series_list = list(
            self.find_series(
                QueryDataset.create(
                    PatientID=patient_id,
                    StudyInstanceUID=study_uid,
                    Modality=modality,
                )
            )
        )

        for series in series_list:
            series_uid = series.SeriesInstanceUID
            modality = series.Modality

            if modality in settings.EXCLUDED_MODALITIES:
                continue

            # TODO maybe we should move the series folder name creation to the
            # store handler as it is not guaranteed that all PACS servers
            # do return the SeriesDescription with C-FIND
            series_folder_name = sanitize_dirname(series.SeriesDescription)
            download_path = Path(dest_folder) / series_folder_name

            self.download_series(patient_id, study_uid, series_uid, download_path, modifier)

        logger.debug("Successfully downloaded study %s.", study_uid)

    def download_series(
        self,
        patient_id: str,
        study_uid: str,
        series_uid: str,
        dest_folder: PathLike,
        modifier: Modifier | None = None,
    ):
        """Download all series to a specified folder for given series UIDs and pseudonymize
        the dataset before storing it to disk."""

        query = QueryDataset.create(
            QueryRetrieveLevel="SERIES",
            PatientID=patient_id,
            StudyInstanceUID=study_uid,
            SeriesInstanceUID=series_uid,
        )

        # We prefer C-GET over WADO-RS over C-MOVE
        if self.server.patient_root_get_support or self.server.study_root_get_support:
            self._download_series_with_c_get(query, dest_folder, modifier)
            logger.debug("Successfully downloaded series %s of study %s.", series_uid, study_uid)
        elif self.server.dicomweb_wado_support:
            self._download_series_with_wado(query, dest_folder, modifier)
            logger.debug("Successfully downloaded series %s of study %s.", series_uid, study_uid)
        elif self.server.patient_root_move_support or self.server.study_root_move_support:
            self._download_series_with_c_move(query, dest_folder, modifier)
            logger.debug("Successfully downloaded series %s of study %s.", series_uid, study_uid)
        else:
            raise ValueError("No Query/Retrieve Information Model supported to download images.")

    def upload_instances(self, resource: PathLike | list[Dataset]):
        """Upload instances from a specified folder or list of instances in memory"""

        if self.server.store_scp_support:
            self.dimse_connector.send_c_store(resource)
        elif self.server.dicomweb_stow_support:
            self.dicom_web_connector.send_stow_rs(resource)
        else:
            raise ValueError("Server does not support uploading images.")

    def move_study(
        self,
        patient_id: str,
        study_uid: str,
        dest_aet: str,
        modality: str = "",
    ):
        series_list = list(
            self.find_series(
                QueryDataset.create(
                    PatientID=patient_id,
                    StudyInstanceUID=study_uid,
                    Modality=modality,
                )
            )
        )

        has_success = False
        has_failure = False
        for series in series_list:
            series_uid = series.SeriesInstanceUID
            modality = series.Modality

            if modality in settings.EXCLUDED_MODALITIES:
                continue

            try:
                self.move_series(
                    patient_id=patient_id,
                    study_uid=study_uid,
                    series_uid=series_uid,
                    dest_aet=dest_aet,
                )
                has_success = True
            except ValueError:
                logger.exception("Failed to move series %s.", series_uid)
                has_failure = True

        if series_list and has_failure:
            if not has_success:
                raise DicomCommunicationError("Failed to move all series.")
            raise DicomCommunicationError("Failed to move some series.")

    def move_series(self, patient_id: str, study_uid: str, series_uid: str, dest_aet: str):
        self.dimse_connector.send_c_move(
            QueryDataset.create(
                QueryRetrieveLevel="SERIES",
                PatientID=patient_id,
                StudyInstanceUID=study_uid,
                SeriesInstanceUID=series_uid,
            ),
            dest_aet,
        )

    def _download_series_with_wado(
        self, query: QueryDataset, dest_folder: PathLike, modifier: Modifier | None = None
    ):
        instances = self.dicom_web_connector.send_wado_rs(query)

        for ds in instances:
            self._handle_downloaded_image(ds, dest_folder, modifier)

    def _download_series_with_c_get(
        self,
        query: QueryDataset,
        dest_folder: PathLike,
        modifier: Modifier | None = None,
    ):
        def handle_c_get_store(event: Event, store_errors: list[Exception]):
            ds = event.dataset
            ds.file_meta = event.file_meta

            try:
                self._handle_downloaded_image(ds, dest_folder, modifier)
            except Exception as err:
                store_errors.append(err)

                # Unfortunately not all PACS servers support or respect a C-CANCEL request,
                # so we abort the association of the C-STORE and C-GET requests manually.
                # See https://github.com/pydicom/pynetdicom/issues/553
                # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
                event.assoc.abort()
                self.dimse_connector.abort_connection()

                return 0xA702  # Out of resources

            return 0x0000  # Success

        self.dimse_connector.send_c_get(query, handle_c_get_store)

    def _download_series_with_c_move(
        self,
        query: QueryDataset,
        dest_folder: PathLike,
        modifier: Modifier | None = None,
    ):
        # When downloading the series with C-MOVE we first must know all the images that
        # the series contains so that we can decide if all were retrieved.
        images = list(
            self.find_images(
                QueryDataset.create(
                    PatientID=query.PatientID,
                    StudyInstanceUID=query.StudyInstanceUID,
                    SeriesInstanceUID=query.SeriesInstanceUID,
                )
            )
        )
        image_uids = [image.SOPInstanceUID for image in images]

        # A list of errors that may occur while receiving the images
        receiving_errors: list[Exception] = []

        # The requested images are sent to the receiver container (a C-STORE SCP server)
        # by the C-MOVE operation. Then those are send via the transmitter (over TCP socket)
        # which we consume in a separate thread.
        with ThreadPoolExecutor() as executor:
            consume_future = executor.submit(
                self._consume_from_receiver,
                query.StudyInstanceUID,
                query.SeriesInstanceUID,
                image_uids,
                dest_folder,
                receiving_errors,
                modifier,
            )

            try:
                self.dimse_connector.send_c_move(query, settings.ADIT_AE_TITLE)

                # We have to check the result of the future here, otherwise
                # exceptions in the thread would be ignored.
                consume_future.result()
            except Exception as err:
                # We check here if an error occurred in the consumer thread and
                # then do nothing here but handle it in the finally block.
                # The consumer might also have aborted the connection which then raises
                # an exception during C-MOVE.
                if receiving_errors:
                    pass

                # Otherwise just raise the original error
                raise err
            finally:
                if receiving_errors:
                    raise receiving_errors[0]

    def _consume_from_receiver(
        self,
        study_uid: str,
        series_uid: str,
        image_uids: list[str],
        dest_folder: PathLike,
        receiving_errors: list[Exception],
        modifier: Modifier | None = None,
    ):
        async def consume():
            remaining_image_uids = image_uids[:]
            last_image_at = time.time()

            file_transmit = FileTransmitClient(
                settings.FILE_TRANSMIT_HOST, settings.FILE_TRANSMIT_PORT
            )

            def check_images_received():
                if remaining_image_uids:
                    if remaining_image_uids == image_uids:
                        logger.error("No images of series %s received.", series_uid)
                        receiving_errors.append(
                            DicomCommunicationError("Failed to download all images with C-MOVE.")
                        )

                    logger.error(
                        "These images of series %s were not received: %s",
                        series_uid,
                        ", ".join(remaining_image_uids),
                    )
                    receiving_errors.append(
                        DicomCommunicationError("Failed to download some images with C-MOVE.")
                    )

            async def handle_received_file(filename: str, metadata: Metadata):
                nonlocal last_image_at
                last_image_at = time.time()

                image_uid = metadata["SOPInstanceUID"]

                try:
                    if image_uid in remaining_image_uids:
                        remaining_image_uids.remove(image_uid)
                        ds = read_dataset(filename)
                        self._handle_downloaded_image(ds, dest_folder, modifier)
                except Exception as err:
                    receiving_errors.append(err)
                finally:
                    await async_os.remove(filename)

                if not remaining_image_uids:
                    return True

                return False

            topic = f"{self.server.ae_title}\\{study_uid}\\{series_uid}"
            subscribe_task = asyncio.create_task(
                file_transmit.subscribe(topic, handle_received_file)
            )

            async def check_timeout():
                while True:
                    await asyncio.sleep(1)

                    if subscribe_task.done():
                        break

                    time_since_last_image = time.time() - last_image_at if last_image_at else 0
                    if time_since_last_image > settings.C_MOVE_DOWNLOAD_TIMEOUT:
                        # Don't accept any more images
                        subscribe_task.cancel()

                        logger.error(
                            "C-MOVE download timed out after %d seconds.",
                            round(time_since_last_image),
                        )

                        # We have to call this before aborting the connection because this
                        # can raise an exception with C-MOVE and we need the info then
                        # if all images were received or not.
                        check_images_received()
                        self.dimse_connector.abort_connection()
                        break

            check_timeout_task = asyncio.create_task(check_timeout())

            await asyncio.gather(subscribe_task, check_timeout_task)

            if not receiving_errors:
                check_images_received()

        asyncio.run(consume(), debug=settings.DEBUG)

    def _handle_downloaded_image(
        self,
        ds: Dataset,
        dest_folder: PathLike,
        modifier: Modifier | None,
    ):
        if modifier:
            modifier(ds)

        folder_path = Path(dest_folder)
        file_path = folder_path / ds.SOPInstanceUID

        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            write_dataset(ds, file_path)
        except Exception as err:
            if isinstance(err, OSError) and err.errno == errno.ENOSPC:
                # No space left on destination
                logger.exception("Out of disk space while saving %s.", file_path)
                no_space_error = OutOfDiskSpaceError(
                    f"Out of disk space on destination '{dest_folder}'."
                )
                no_space_error.__cause__ = err
                raise no_space_error
            else:
                logger.exception("Failed to save %s.", file_path)
                raise err
