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
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from os import PathLike

from aiofiles import os as async_os
from django.conf import settings
from pydicom import Dataset
from pynetdicom.events import Event

from ..errors import DicomError, IncompleteFetchError, RetriableDicomError
from ..models import DicomServer
from ..types import DicomLogEntry
from .dicom_dataset import QueryDataset, ResultDataset
from .dicom_utils import (
    convert_to_python_regex,
    has_wildcards,
    read_dataset,
)
from .dicom_web_connector import DicomWebConnector
from .dimse_connector import DimseConnector
from .file_transmit import FileTransmitClient, Metadata

logger = logging.getLogger(__name__)


class DicomOperator:
    def __init__(
        self,
        server: DicomServer,
        persistent: bool = False,
        dimse_timeout: int | None = 60,
    ):
        self.server = server
        self.dimse_connector = DimseConnector(
            server,
            auto_close=not persistent,
            dimse_timeout=dimse_timeout,
        )
        # TODO: also make retries and timeouts possible in DicomWebConnector
        self.dicom_web_connector = DicomWebConnector(server)

        self.logs: list[DicomLogEntry] = []

    def get_logs(self) -> list[DicomLogEntry]:
        return self.dimse_connector.logs + self.dicom_web_connector.logs + self.logs

    def close(self) -> None:
        try:
            if self.dimse_connector.assoc:
                self.dimse_connector.close_connection()
        except Exception:
            logger.debug("Error closing DIMSE association", exc_info=True)

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

        Args:
            query: The query dataset.
            limit_results: The maximum number of results to return.
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
            raise DicomError("No supported method to find patients available.")

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
                patient_name_pattern = convert_to_python_regex(
                    query.PatientName, case_insensitive=True
                )
                if not patient_name_pattern.fullmatch(result.PatientName):
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

        Args:
            query: The query dataset.
            limit_results: The maximum number of results to return.
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
            raise DicomError("No supported method to find studies available.")

    def _handle_found_studies(
        self,
        query: QueryDataset,
        results: Iterable[ResultDataset],
    ) -> Iterator[ResultDataset]:
        for result in results:
            # Optionally filter by its study description, if the server doesn't support it
            if query.has("StudyDescription"):
                study_description_pattern = convert_to_python_regex(query.StudyDescription)
                if not study_description_pattern.fullmatch(result.StudyDescription):
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

        Args:
            query: The query dataset.
            limit_results: The maximum number of results to return.
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

        study_uid = query.get("StudyInstanceUID")
        if not study_uid or has_wildcards(study_uid):
            raise DicomError("A valid StudyInstanceUID is required for querying series.")

        query.QueryRetrieveLevel = "SERIES"

        if self.server.patient_root_find_support or self.server.study_root_find_support:
            if not self.server.study_root_find_support:
                patient_id = query.get("PatientID")
                if not patient_id or has_wildcards(patient_id):
                    raise DicomError(
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
                if not series_description_pattern.fullmatch(result.SeriesDescription):
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

        Args:
            query: The query dataset.
            limit_results: The maximum number of results to return.
        """
        query.ensure_elements(
            "PatientID",
            "StudyInstanceUID",
            "SeriesInstanceUID",
            "SOPInstanceUID",
            "InstanceNumber",
            "InstanceAvailability",
        )

        study_uid = query.get("StudyInstanceUID")
        if not study_uid or has_wildcards(study_uid):
            raise DicomError("A valid StudyInstanceUID is required for querying images.")
        series_uid = query.get("SeriesInstanceUID")
        if not series_uid or has_wildcards(series_uid):
            raise DicomError("A valid SeriesInstanceUID is required for querying images.")

        query.QueryRetrieveLevel = "IMAGE"

        if self.server.patient_root_find_support or self.server.study_root_find_support:
            if not self.server.study_root_find_support:
                patient_id = query.get("PatientID")
                if not patient_id or has_wildcards(patient_id):
                    raise DicomError(
                        "PatientID is required for querying images with "
                        "Patient Root Query/Retrieve Information Model."
                    )

            yield from self.dimse_connector.send_c_find(query, limit_results=limit_results)
        elif self.server.dicomweb_qido_support:
            yield from self.dicom_web_connector.send_qido_rs(query, limit_results=limit_results)
        else:
            raise DicomError("No supported method to find images available.")

    def fetch_study(
        self,
        patient_id: str,
        study_uid: str,
        callback: Callable[[Dataset], None],
    ):
        """Fetch a study.

        Args:
            patient_id: The patient ID.
            study_uid: The study instance UID.
            callback: A callback function that is called for each fetched image.
        """
        query = QueryDataset.create(
            QueryRetrieveLevel="STUDY",
            PatientID=patient_id,
            StudyInstanceUID=study_uid,
        )

        if self.server.dicomweb_wado_support:
            self._fetch_images_with_wado_rs(query, callback)
        elif self.server.patient_root_get_support or self.server.study_root_get_support:
            self._fetch_images_with_c_get(query, callback)
        elif self.server.patient_root_move_support or self.server.study_root_move_support:
            self._fetch_images_with_c_move(query, callback)
        else:
            raise DicomError("No supported method to fetch a study available.")

        logger.debug("Successfully downloaded study %s.", study_uid)

    def fetch_series(
        self,
        patient_id: str,
        study_uid: str,
        series_uid: str,
        callback: Callable[[Dataset], None],
    ) -> None:
        """Fetch a series.

        Args:
            patient_id: The patient ID.
            study_uid: The study instance UID.
            series_uid: The series instance UID.
            callback: A callback function that is called for each fetched image.
        """

        query = QueryDataset.create(
            QueryRetrieveLevel="SERIES",
            PatientID=patient_id,
            StudyInstanceUID=study_uid,
            SeriesInstanceUID=series_uid,
        )

        # We prefer WADO-RS over C-GET over C-MOVE
        if self.server.dicomweb_wado_support:
            self._fetch_images_with_wado_rs(query, callback)
        elif self.server.patient_root_get_support or self.server.study_root_get_support:
            self._fetch_images_with_c_get(query, callback)
        elif self.server.patient_root_move_support or self.server.study_root_move_support:
            self._fetch_images_with_c_move(query, callback)
        else:
            raise DicomError("No supported method to fetch a series available.")

    def fetch_image(
        self,
        patient_id: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
        callback: Callable[[Dataset], None],
    ) -> None:
        """Download an image.

        Args:
            patient_id: The patient ID.
            study_uid: The study instance UID.
            series_uid: The series instance UID.
            image_uid: The SOP instance UID.
            callback: A callback function that is called for the fetched image.
        """

        query = QueryDataset.create(
            QueryRetrieveLevel="IMAGE",
            PatientID=patient_id,
            StudyInstanceUID=study_uid,
            SeriesInstanceUID=series_uid,
            SOPInstanceUID=image_uid,
        )

        # We prefer WADO-RS over C-GET over C-MOVE
        if self.server.dicomweb_wado_support:
            self._fetch_images_with_wado_rs(query, callback)
        elif self.server.patient_root_get_support or self.server.study_root_get_support:
            self._fetch_images_with_c_get(query, callback)
        elif self.server.patient_root_move_support or self.server.study_root_move_support:
            self._fetch_images_with_c_move(query, callback)
        else:
            raise DicomError("No supported method to fetch an image available.")

    def upload_images(self, resource: PathLike | list[Dataset]) -> None:
        """Upload images from a specified folder or list of images in memory"""

        if self.server.store_scp_support:
            self.dimse_connector.send_c_store(resource)
        elif self.server.dicomweb_stow_support:
            self.dicom_web_connector.send_stow_rs(resource)
        else:
            raise DicomError("No supported method to upload images available.")

    def move_study(
        self,
        patient_id: str,
        study_uid: str,
        dest_aet: str,
    ) -> None:
        """Move a study to another DICOM server.

        Args:
            patient_id: The patient ID.
            study_uid: The study instance UID.
            dest_aet: The destination AE title.
            modality: The modality of the series to move.
        """
        if not self.server.patient_root_move_support and not self.server.study_root_move_support:
            raise DicomError("The server does not support moving a study.")

        self.dimse_connector.send_c_move(
            QueryDataset.create(
                QueryRetrieveLevel="STUDY",
                PatientID=patient_id,
                StudyInstanceUID=study_uid,
            ),
            dest_aet,
        )

    def move_series(self, patient_id: str, study_uid: str, series_uid: str, dest_aet: str) -> None:
        """Move a series to another DICOM server.

        Args:
            patient_id: The patient ID.
            study_uid: The study instance UID.
            series_uid: The series instance UID.
            dest_aet: The destination AE title.
        """
        if not self.server.patient_root_move_support and not self.server.study_root_move_support:
            raise DicomError("The server does not support moving a series.")

        self.dimse_connector.send_c_move(
            QueryDataset.create(
                QueryRetrieveLevel="SERIES",
                PatientID=patient_id,
                StudyInstanceUID=study_uid,
                SeriesInstanceUID=series_uid,
            ),
            dest_aet,
        )

    def _fetch_images_with_wado_rs(
        self, query: QueryDataset, callback: Callable[[Dataset], None]
    ) -> None:
        images = self.dicom_web_connector.send_wado_rs(query)
        for ds in images:
            self._handle_fetched_image(ds, callback)

    def _fetch_images_with_c_get(
        self, query: QueryDataset, callback: Callable[[Dataset], None]
    ) -> None:
        def store_handler(event: Event, store_errors: list[Exception]) -> int:
            ds = event.dataset
            ds.file_meta = event.file_meta

            try:
                self._handle_fetched_image(ds, callback)
            except Exception as err:
                logger.error(
                    "Store handler failed for SOP %s: %s",
                    ds.SOPInstanceUID,
                    err,
                    exc_info=True,
                )
                store_errors.append(err)

                # Unfortunately not all PACS servers support or respect a C-CANCEL request,
                # so we abort the association of the C-STORE and C-GET requests manually.
                # See https://github.com/pydicom/pynetdicom/issues/553
                # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
                event.assoc.abort()
                self.dimse_connector.abort_connection()

                return 0xA702  # Out of resources

            return 0x0000  # Success

        store_errors: list[Exception] = []

        self.dimse_connector.send_c_get(query, store_handler, store_errors)

        if store_errors:
            raise store_errors[0]

    def _fetch_images_with_c_move(
        self,
        query: QueryDataset,
        callback: Callable[[Dataset], None],
    ) -> None:
        # When downloading images with C-MOVE we first must know all the SOPInstanceUIDs
        # in advance so that we can check if all were received. Their SeriesInstanceUIDs
        # are needed to fetch missing images again.
        image_uids: dict[str, str]  # SOPInstanceUID -> SeriesInstanceUID
        if image_uid := query.get("SOPInstanceUID"):
            image_uids = {image_uid: query.SeriesInstanceUID}
        elif series_uid := query.get("SeriesInstanceUID"):
            query_dataset = QueryDataset.create(
                PatientID=query.PatientID,
                StudyInstanceUID=query.StudyInstanceUID,
                SeriesInstanceUID=series_uid,
            )
            images = self.find_images(query_dataset)
            image_uids = {image.SOPInstanceUID: series_uid for image in images}
        else:
            # If SeriesInstanceUID not provided or needed it is still necessary for
            # querying on IMAGE level
            query_dataset = QueryDataset.create(
                PatientID=query.PatientID,
                StudyInstanceUID=query.StudyInstanceUID,
            )

            # Collected first, as the image queries below use the same association, which
            # must not get a new C-FIND while the series query still streams its results.
            series_list = list(self.find_series(query_dataset))

            image_uids = {
                image.SOPInstanceUID: series.SeriesInstanceUID
                for series in series_list
                for image in self.find_images(
                    QueryDataset.create(
                        PatientID=query.PatientID,
                        StudyInstanceUID=query.StudyInstanceUID,
                        SeriesInstanceUID=series.SeriesInstanceUID,
                    )
                )
            }

        # The images not received yet, the consumer removes each one it handed over
        missing_images = dict(image_uids)

        # When the consumer last received an expected image
        last_image_at = [time.monotonic()]

        # A list of errors that may occur while receiving the images
        receiving_errors: list[Exception] = []

        # An event to signal that the receiver registered our subscription
        subscribed_event = threading.Event()

        # An event to make sure the consumer thread finally stops
        stop_consumer_event = threading.Event()

        # The requested images are sent to the receiver container (a C-STORE SCP server)
        # by the C-MOVE operation. Then those are send via the transmitter (over TCP socket)
        # which we consume in a separate thread.
        with ThreadPoolExecutor(max_workers=1) as executor:
            consume_future = executor.submit(
                self._consume_from_receiver,
                query.StudyInstanceUID,
                missing_images,
                last_image_at,
                callback,
                subscribed_event,
                stop_consumer_event,
                receiving_errors,
            )

            try:
                # Images the PACS sends before the receiver knows about us would be discarded
                self._wait_for_subscription(subscribed_event, consume_future)

                self.dimse_connector.send_c_move(query, settings.RECEIVER_AE_TITLE)
                self._wait_for_images(
                    missing_images,
                    last_image_at,
                    time.monotonic(),
                    consume_future,
                    receiving_errors,
                )

                # When nothing or most of it arrived, the delivery is broken as a whole (or the
                # PACS is overloaded), so one C-MOVE per image would only add load. The
                # download fails instead and is retried as a whole.
                delivery_broken = bool(missing_images) and (
                    len(missing_images) == len(image_uids)
                    or 100 * len(missing_images) / len(image_uids)
                    > settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT
                )

                for _ in range(0 if delivery_broken else settings.C_MOVE_REFETCH_ATTEMPTS):
                    if not missing_images or receiving_errors or consume_future.done():
                        break
                    self._refetch_missing_images(
                        query, missing_images, consume_future, receiving_errors
                    )
                    self._wait_for_images(
                        missing_images,
                        last_image_at,
                        time.monotonic(),
                        consume_future,
                        receiving_errors,
                    )

                if not receiving_errors:
                    self._check_images_received(
                        query.StudyInstanceUID, image_uids, missing_images, delivery_broken
                    )
            except Exception as err:
                # We check here if an error occurred in the consumer thread and
                # and only re-raise the error when non occurred.
                # The consumer might also have aborted the connection which then raises
                # an exception during C-MOVE.
                # Errors in the consumer thread are handled in the finally block.
                if not receiving_errors:
                    raise err
            finally:
                stop_consumer_event.set()

                if receiving_errors:
                    raise receiving_errors[0]

                # A failure of the consumer itself, not of receiving an image
                if consume_future.done() and (consumer_error := consume_future.exception()):
                    raise consumer_error

    def _wait_for_subscription(
        self, subscribed_event: threading.Event, consume_future: Future[None]
    ) -> None:
        deadline = time.monotonic() + settings.C_MOVE_SUBSCRIBE_TIMEOUT
        while not subscribed_event.wait(timeout=0.1):
            if consume_future.done() or time.monotonic() > deadline:
                raise RetriableDicomError("Could not subscribe to the DICOM receiver.")

    def _refetch_missing_images(
        self,
        query: QueryDataset,
        missing_images: dict[str, str],
        consume_future: Future[None],
        receiving_errors: list[Exception],
    ) -> None:
        # The images are the same a SERIES or STUDY level C-MOVE sends (one C-STORE each),
        # but every C-MOVE costs the PACS a query resolution and its own association to the
        # receiver. Many of them in a row can strain a PACS (association limits, empty
        # SUCCESS responses under rapid association requests, see DimseConnector). So they
        # share one association, are not retried (the re-fetch rounds are the retries) and
        # a lost association ends the round, leaving it to the task retry.
        logger.info(
            "Fetching %d missing images of study %s again.",
            len(missing_images),
            query.StudyInstanceUID,
        )

        def image_queries() -> Iterator[QueryDataset]:
            # A copy, as the consumer thread removes images that arrive meanwhile
            for image_uid, series_uid in missing_images.copy().items():
                if receiving_errors or consume_future.done():
                    return
                if image_uid in missing_images:
                    yield QueryDataset.create(
                        QueryRetrieveLevel="IMAGE",
                        PatientID=query.PatientID,
                        StudyInstanceUID=query.StudyInstanceUID,
                        SeriesInstanceUID=series_uid,
                        SOPInstanceUID=image_uid,
                    )

        self.dimse_connector.send_c_move_batch(image_queries(), settings.RECEIVER_AE_TITLE)

    def _wait_for_images(
        self,
        missing_images: dict[str, str],
        last_image_at: list[float],
        moves_finished_at: float,
        consume_future: Future[None],
        receiving_errors: list[Exception],
    ) -> None:
        """Wait until all images arrived or none for C_MOVE_DOWNLOAD_TIMEOUT.

        The timeout starts when the C-MOVE operations finished at the earliest, as the
        receiver may still deliver images the PACS already sent.
        """
        while missing_images and not receiving_errors and not consume_future.done():
            idle_time = time.monotonic() - max(last_image_at[0], moves_finished_at)
            if idle_time > settings.C_MOVE_DOWNLOAD_TIMEOUT:
                logger.warning("C-MOVE download timed out after %d seconds.", round(idle_time))
                return
            time.sleep(0.1)

    def _check_images_received(
        self,
        study_uid: str,
        image_uids: dict[str, str],
        missing_images: dict[str, str],
        delivery_broken: bool,
    ) -> None:
        if not missing_images:
            return

        if len(missing_images) == len(image_uids):
            logger.error("No images of study %s received.", study_uid)
            raise RetriableDicomError("Failed to fetch all images with C-MOVE.")

        logger.warning(
            "These images of study %s were not received: %s",
            study_uid,
            ", ".join(missing_images),
        )

        if delivery_broken:
            raise RetriableDicomError(
                f"{len(missing_images)} of {len(image_uids)} images of study {study_uid} "
                "could not be fetched with C-MOVE, too many to fetch them again one by one."
            )

        if settings.C_MOVE_FAIL_ON_INCOMPLETE:
            raise IncompleteFetchError(study_uid, list(missing_images), len(image_uids))

        self.logs.append(
            {
                "level": "Warning",
                "title": "Some images could not be fetched",
                "message": "Failed to fetch some images with C-MOVE.",
            }
        )

    def _consume_from_receiver(
        self,
        study_uid: str,
        missing_images: dict[str, str],
        last_image_at: list[float],
        callback: Callable[[Dataset], None],
        subscribed_event: threading.Event,
        stop_consumer_event: threading.Event,
        receiving_errors: list[Exception],
    ) -> None:
        async def consume():
            file_transmit = FileTransmitClient(
                settings.FILE_TRANSMIT_HOST, settings.FILE_TRANSMIT_PORT
            )

            def read_and_handle_image(filename: str):
                ds = read_dataset(filename)
                self._handle_fetched_image(ds, callback)

            async def handle_received_file(filename: str, metadata: Metadata):
                image_uid = metadata["SOPInstanceUID"]

                try:
                    # Duplicates and images of other fetches of the same study are ignored
                    # and must not keep the wait for the missing images alive.
                    if image_uid in missing_images:
                        last_image_at[0] = time.monotonic()
                        # Good to know, exceptions will be propagated by asyncio.to_thread
                        await asyncio.to_thread(read_and_handle_image, filename)
                        # Only removed once handed over, so that the image doesn't count as
                        # received while it is still processed.
                        del missing_images[image_uid]
                        last_image_at[0] = time.monotonic()
                except Exception as err:
                    receiving_errors.append(err)
                finally:
                    await async_os.remove(filename)

                return not missing_images

            subscribe_task = asyncio.create_task(
                file_transmit.subscribe(
                    study_uid, handle_received_file, subscribed_handler=subscribed_event.set
                )
            )

            while True:
                await asyncio.sleep(0.1)

                if stop_consumer_event.is_set():
                    subscribe_task.cancel()
                    break

                if subscribe_task.done():
                    if err := subscribe_task.exception():
                        error = RetriableDicomError("Connection to the DICOM receiver failed.")
                        error.__cause__ = err
                        receiving_errors.append(error)
                    break

        asyncio.run(consume(), debug=settings.DEBUG)

    def _handle_fetched_image(self, ds: Dataset, callback: Callable[[Dataset], None]) -> None:
        try:
            callback(ds)
        except Exception as err:
            if isinstance(err, OSError) and err.errno == errno.ENOSPC:
                # No space left on destination
                raise DicomError(
                    f"Out of disk space while trying to save '{err.filename}'."
                ) from err
            else:
                # Unknown error
                raise DicomError(f"Failed to handle image '{ds.SOPInstanceUID}'.") from err
