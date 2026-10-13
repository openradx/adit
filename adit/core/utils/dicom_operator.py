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
import itertools
import logging
import queue
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
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
from .file_transmit import REPLAY_SYNC_TOKEN, FileTransmitClient, Metadata

logger = logging.getLogger(__name__)


@dataclass
class _CMoveFetch:
    """The state of one C-MOVE download, shared by the worker and its consumer thread.

    Without IMAGE-level queries, the images of each series are counted instead of listed, as
    far as the PACS reports how many there are.
    """

    server: DicomServer
    query: QueryDataset
    # The listed images: SOPInstanceUID -> SeriesInstanceUID
    image_uids: dict[str, str]
    # The counted series: SeriesInstanceUID -> image count, if the PACS reports it
    series_counts: dict[str, int | None]
    # The listed images not received yet, the consumer removes each one it handed over
    missing_images: dict[str, str] = field(init=False)
    # The images the consumer handed over: SOPInstanceUID -> SeriesInstanceUID (if known)
    received: dict[str, str | None] = field(default_factory=dict)
    # How many images the PACS reports its C-MOVE sent
    reported: int | None = None
    # When the consumer last handed over an image
    last_image_at: float = field(default_factory=time.monotonic)
    # When the consumer last received any image of this fetch. Duplicates count too, as a
    # PACS sends the whole study again when a C-MOVE is retried, but images of other series
    # of a series fetch don't.
    last_received_at: float = field(default_factory=time.monotonic)
    # Sync requests the consumer sends to the receiver, the tokens it confirmed, and the
    # images still missing at the last confirmation
    sync_requests: queue.SimpleQueue[str] = field(default_factory=queue.SimpleQueue)
    synced_tokens: set[str] = field(default_factory=set)
    missing_at_sync: set[str] = field(default_factory=set)
    tokens: Iterator[int] = field(default_factory=itertools.count)
    # Errors while receiving the images
    receiving_errors: list[Exception] = field(default_factory=list)
    # Set once the receiver registered the subscription
    subscribed: threading.Event = field(default_factory=threading.Event)
    # Set to make sure the consumer thread finally stops
    stop_consumer: threading.Event = field(default_factory=threading.Event)
    # The thread that consumes the images from the receiver
    consumer: Future[None] = field(init=False)
    # The AE titles of images skipped as the server doesn't accept them, logged once
    rejected_calling_ae_titles: set[str | None] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.missing_images = dict(self.image_uids)

    def receiving(self) -> bool:
        return not self.receiving_errors and not self.consumer.done()

    def in_scope(self, metadata: Metadata) -> bool:
        calling_ae_title = metadata.get("CallingAETitle")
        if not self.server.accepts_calling_ae_title(calling_ae_title):
            if calling_ae_title not in self.rejected_calling_ae_titles:
                self.rejected_calling_ae_titles.add(calling_ae_title)
                logger.warning(
                    "Skipping images of study %s from AE title %s, which is not accepted for %s.",
                    self.query.StudyInstanceUID,
                    calling_ae_title,
                    self.server.ae_title,
                )
            return False
        # Besides the listed images, every image of the requested study or series belongs to
        # the fetch, as the IMAGE-level C-FIND of some PACS silently caps its results
        if metadata["SOPInstanceUID"] in self.image_uids:
            return True
        if self.query.get("SOPInstanceUID"):
            return False
        series_uid = self.query.get("SeriesInstanceUID")
        return not series_uid or metadata.get("SeriesInstanceUID") == series_uid

    def series_count(self, series_uid: str) -> int:
        # A series the C-FIND found holds an image at least, also without a count
        return max(self.series_counts[series_uid] or 0, 1)

    def expected_count(self) -> int:
        return max(
            len(self.image_uids),
            self.reported or 0,
            sum(self.series_count(series_uid) for series_uid in self.series_counts),
        )

    def short_series(self) -> dict[str, int]:
        # Copied first, as the consumer adds to it meanwhile
        received_per_series = Counter(list(self.received.values()))
        shortfalls = {
            uid: self.series_count(uid) - received_per_series[uid] for uid in self.series_counts
        }
        return {uid: shortfall for uid, shortfall in shortfalls.items() if shortfall > 0}

    def missing_count(self) -> int:
        # Images the PACS reports beyond the listed or counted ones that arrived are missing
        # too, though it is unknown which ones
        return max(
            len(self.missing_images),
            sum(self.short_series().values()),
            (self.reported or 0) - len(self.received),
        )

    def delivery_broken(self) -> bool:
        # When nothing or most of it arrived, the delivery is broken as a whole (or the PACS
        # is overloaded), so one C-MOVE per image would only add load. The download fails
        # instead and is retried as a whole.
        return bool(self.missing_count()) and (
            not self.received
            or 100 * self.missing_count() / self.expected_count()
            > settings.C_MOVE_REFETCH_MAX_MISSING_PERCENT
        )


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
        # The PACS sends the requested images to the receiver container (a C-STORE SCP), which
        # forwards them over a TCP socket to the consumer thread.
        fetch = self._list_c_move_images(query)
        with ThreadPoolExecutor(max_workers=1) as executor:
            fetch.consumer = executor.submit(self._consume_from_receiver, fetch, callback)
            try:
                # Images the PACS sends before the receiver knows about us would be discarded
                self._wait_for_subscription(fetch)
                self._move(fetch)
                delivery_broken = fetch.delivery_broken()
                if not delivery_broken:
                    self._refetch(fetch)
                if not fetch.receiving_errors:
                    self._check_images_received(fetch, delivery_broken)
            except Exception as err:
                # The consumer may have ended the connection, which then fails the C-MOVE. Its
                # errors are raised in the finally block instead.
                if not fetch.receiving_errors:
                    raise err
            finally:
                fetch.stop_consumer.set()

                if fetch.receiving_errors:
                    raise fetch.receiving_errors[0]

                # A failure of the consumer itself, not of receiving an image
                if fetch.consumer.done() and (consumer_error := fetch.consumer.exception()):
                    raise consumer_error

    def _list_c_move_images(self, query: QueryDataset) -> _CMoveFetch:
        """List the images to fetch, so that it can be checked that all arrived.

        Their SeriesInstanceUIDs are needed to fetch missing images again. Without IMAGE-level
        queries, the series are counted instead.
        """
        image_uids: dict[str, str] = {}
        series_counts: dict[str, int | None] = {}
        if image_uid := query.get("SOPInstanceUID"):
            image_uids = {image_uid: query.SeriesInstanceUID}
        elif not self.server.image_level_find_support:
            series_counts = self._count_series_images(query)
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
        return _CMoveFetch(self.server, query, image_uids, series_counts)

    def _count_series_images(self, query: QueryDataset) -> dict[str, int | None]:
        """The series of the query, each with its image count if the PACS returns it."""
        series_query = QueryDataset.create(
            PatientID=query.PatientID, StudyInstanceUID=query.StudyInstanceUID
        )
        if series_uid := query.get("SeriesInstanceUID"):
            series_query = QueryDataset.create(
                PatientID=query.PatientID,
                StudyInstanceUID=query.StudyInstanceUID,
                SeriesInstanceUID=series_uid,
            )

        series_counts: dict[str, int | None] = {}
        for series in list(self.find_series(series_query)):
            try:
                count = int(series.get("NumberOfSeriesRelatedInstances"))
            except (TypeError, ValueError):
                # Not returned, or not a number
                count = None
            series_counts[series.SeriesInstanceUID] = count
        return series_counts

    def _wait_for_subscription(self, fetch: _CMoveFetch) -> None:
        deadline = time.monotonic() + settings.C_MOVE_SUBSCRIBE_TIMEOUT
        while not fetch.subscribed.wait(timeout=0.1):
            if fetch.consumer.done() or time.monotonic() > deadline:
                raise RetriableDicomError("Could not subscribe to the DICOM receiver.")

    def _move(self, fetch: _CMoveFetch) -> None:
        """Send the C-MOVE and wait until it is known which of its images didn't arrive."""
        query = fetch.query
        fetch.reported = self.dimse_connector.send_c_move(
            query,
            settings.RECEIVER_AE_TITLE,
            last_activity=lambda: fetch.last_received_at,
        )
        if fetch.image_uids and (fetch.reported or 0) > len(fetch.image_uids):
            logger.warning(
                "The IMAGE-level C-FIND of %s listed %d images of study %s, but its C-MOVE "
                "sent %d. Its C-FIND results may be capped (see the image level find support "
                "of the server).",
                self.server.ae_title,
                len(fetch.image_uids),
                query.StudyInstanceUID,
                fetch.reported,
            )
        series_uid = query.get("SeriesInstanceUID")
        if fetch.reported is not None and series_uid in fetch.series_counts:
            # What the PACS sent of the series counts once it is more than the series' count,
            # a lower one only after a re-fetch (the first C-MOVE may have failed in part only
            # for a while)
            count = fetch.series_counts[series_uid]
            if count is None or fetch.reported > count:
                fetch.series_counts[series_uid] = fetch.reported

        if not fetch.image_uids:
            # Images that are not known nor counted are only waited for until the receiver
            # confirmed what it got
            self._sync_with_receiver(fetch, str(next(fetch.tokens)), stop_when_complete=False)
            if fetch.reported is None and all(c is None for c in fetch.series_counts.values()):
                logger.info(
                    "The completeness of study %s can't be checked beyond an image per series, "
                    "as %s reports neither image counts nor C-MOVE sub-operations.",
                    query.StudyInstanceUID,
                    self.server.ae_title,
                )

        self._wait_for_delivery(fetch)

    def _refetch(self, fetch: _CMoveFetch) -> None:
        # Listed images are requested again one by one, counted ones with their series. Images
        # that are neither are unknown.
        for _ in range(settings.C_MOVE_REFETCH_ATTEMPTS):
            if not fetch.receiving():
                return
            if fetch.missing_images:
                self._refetch_missing_images(fetch)
            elif fetch.short_series():
                self._refetch_short_series(fetch)
            else:
                return
            self._wait_for_delivery(fetch)

    def _refetch_missing_images(self, fetch: _CMoveFetch) -> None:
        # The images are the same a SERIES or STUDY level C-MOVE sends (one C-STORE each),
        # but every C-MOVE costs the PACS a query resolution and its own association to the
        # receiver. Many of them in a row can strain a PACS (association limits, empty
        # SUCCESS responses under rapid association requests, see DimseConnector). So they
        # share one association, are not retried (the re-fetch rounds are the retries) and
        # a lost association ends the round, leaving it to the task retry.
        query = fetch.query
        logger.info(
            "Fetching %d missing images of study %s again.",
            len(fetch.missing_images),
            query.StudyInstanceUID,
        )

        def image_queries() -> Iterator[QueryDataset]:
            # A copy, as the consumer thread removes images that arrive meanwhile
            for image_uid, series_uid in fetch.missing_images.copy().items():
                if not fetch.receiving():
                    return
                if image_uid in fetch.missing_images:
                    # Requested again, so its arrival is expected and not late
                    fetch.missing_at_sync.discard(image_uid)
                    yield QueryDataset.create(
                        QueryRetrieveLevel="IMAGE",
                        PatientID=query.PatientID,
                        StudyInstanceUID=query.StudyInstanceUID,
                        SeriesInstanceUID=series_uid,
                        SOPInstanceUID=image_uid,
                    )

        self.dimse_connector.send_c_move_batch(
            image_queries(),
            settings.RECEIVER_AE_TITLE,
            last_activity=lambda: fetch.last_received_at,
        )

    def _refetch_short_series(self, fetch: _CMoveFetch) -> None:
        # Like the IMAGE-level re-fetch (see there), but one SERIES-level C-MOVE for each series
        # with images missing. What the PACS reports as sent then counts for that series, as
        # its image count may include images it can't send.
        query = fetch.query
        series_uids = list(fetch.short_series())
        logger.info(
            "Fetching %d series of study %s again, as images of them are missing.",
            len(series_uids),
            query.StudyInstanceUID,
        )

        def series_queries() -> Iterator[QueryDataset]:
            for series_uid in series_uids:
                if not fetch.receiving():
                    return
                yield QueryDataset.create(
                    QueryRetrieveLevel="SERIES",
                    PatientID=query.PatientID,
                    StudyInstanceUID=query.StudyInstanceUID,
                    SeriesInstanceUID=series_uid,
                )

        reported = self.dimse_connector.send_c_move_batch(
            series_queries(),
            settings.RECEIVER_AE_TITLE,
            last_activity=lambda: fetch.last_received_at,
        )
        for series_uid, count in zip(series_uids, reported):
            if count is not None:
                fetch.series_counts[series_uid] = count

    def _wait_for_delivery(self, fetch: _CMoveFetch) -> None:
        """Wait until it is known which images of the C-MOVE operations didn't arrive.

        The receiver confirms when it has forwarded everything it got before our sync request,
        which follows the final C-MOVE response, so its delays can't make images count as
        missing. Images still missing then are waited for C_MOVE_DOWNLOAD_TIMEOUT, as some PACS
        send images after their final C-MOVE response, and the receiver is asked again. They
        count as missing once such a round brought nothing new. The receiver's confirmation is
        read only after every image sent before it was handed over, so asking again also waits
        for a slow callback.
        """

        received_before: int | None = None
        while fetch.missing_count() and fetch.receiving():
            synced_at = self._sync_with_receiver(fetch, str(next(fetch.tokens)))
            if synced_at is None or not fetch.missing_count():
                return

            if received_before is not None and len(fetch.received) == received_before:
                logger.info(
                    "%d images of study %s did not arrive within %d s after the receiver "
                    "confirmed the delivery.",
                    fetch.missing_count(),
                    fetch.query.StudyInstanceUID,
                    settings.C_MOVE_DOWNLOAD_TIMEOUT,
                )
                return

            received_before = len(fetch.received)
            self._wait_for_late_images(fetch, synced_at)

    def _sync_with_receiver(
        self, fetch: _CMoveFetch, token: str, stop_when_complete: bool = True
    ) -> float | None:
        """Wait for the receiver to confirm the sync request with this token.

        Returns when it was confirmed, or None if there is nothing to wait for anymore.
        """
        fetch.sync_requests.put(token)
        requested_at = time.monotonic()
        while (fetch.missing_count() or not stop_when_complete) and fetch.receiving():
            if token in fetch.synced_tokens:
                return time.monotonic()

            # Every image of this fetch received meanwhile, duplicates too, was queued before
            # the confirmation, so it brings the confirmation closer
            idle_time = time.monotonic() - max(
                fetch.last_image_at, fetch.last_received_at, requested_at
            )
            if idle_time > settings.C_MOVE_SYNC_TIMEOUT:
                raise RetriableDicomError(
                    "The DICOM receiver did not confirm the delivery of study "
                    f"{fetch.query.StudyInstanceUID} in time."
                )
            time.sleep(0.1)
        return None

    def _wait_for_late_images(self, fetch: _CMoveFetch, synced_at: float) -> None:
        while fetch.missing_count() and fetch.receiving():
            idle_time = time.monotonic() - max(fetch.last_image_at, synced_at)
            if idle_time > settings.C_MOVE_DOWNLOAD_TIMEOUT:
                return
            time.sleep(0.1)

    def _check_images_received(self, fetch: _CMoveFetch, delivery_broken: bool) -> None:
        missing_count = fetch.missing_count()
        if not missing_count:
            return

        study_uid = fetch.query.StudyInstanceUID
        if not fetch.received:
            logger.error("No images of study %s received.", study_uid)
            raise RetriableDicomError("Failed to fetch all images with C-MOVE.")

        expected_count = fetch.expected_count()
        logger.warning(
            "%d of %d images of study %s were not received: %s",
            missing_count,
            expected_count,
            study_uid,
            ", ".join(fetch.missing_images) or "unknown which ones",
        )

        if delivery_broken:
            raise RetriableDicomError(
                f"{missing_count} of {expected_count} images of study {study_uid} "
                "could not be fetched with C-MOVE, too many to fetch them again one by one."
            )

        if settings.C_MOVE_FAIL_ON_INCOMPLETE:
            raise IncompleteFetchError(
                study_uid, missing_count, expected_count, list(fetch.missing_images)
            )

        self.logs.append(
            {
                "level": "Warning",
                "title": "Some images could not be fetched",
                "message": "Failed to fetch some images with C-MOVE.",
            }
        )

    def _consume_from_receiver(
        self, fetch: _CMoveFetch, callback: Callable[[Dataset], None]
    ) -> None:
        study_uid = fetch.query.StudyInstanceUID

        async def consume():
            late_logged = False

            file_transmit = FileTransmitClient(
                settings.FILE_TRANSMIT_HOST, settings.FILE_TRANSMIT_PORT
            )

            def read_and_handle_image(filename: str):
                ds = read_dataset(filename)
                self._handle_fetched_image(ds, callback)

            async def handle_received_file(filename: str, metadata: Metadata):
                nonlocal late_logged
                image_uid = metadata["SOPInstanceUID"]
                in_scope = fetch.in_scope(metadata)
                if in_scope:
                    fetch.last_received_at = time.monotonic()

                try:
                    # Duplicates and images of other series of a series fetch are ignored
                    # and must not keep the wait for the missing images alive.
                    if in_scope and image_uid not in fetch.received:
                        if image_uid in fetch.missing_at_sync:
                            fetch.missing_at_sync.discard(image_uid)
                            if not late_logged:
                                late_logged = True
                                logger.info(
                                    "Image %s of study %s arrived after the receiver confirmed "
                                    "the delivery: the PACS sends images after its final C-MOVE "
                                    "response, or a C-MOVE of the round failed.",
                                    image_uid,
                                    study_uid,
                                )
                        fetch.last_image_at = time.monotonic()
                        # Good to know, exceptions will be propagated by asyncio.to_thread
                        await asyncio.to_thread(read_and_handle_image, filename)
                        # Only removed once handed over, so that the image doesn't count as
                        # received while it is still processed.
                        fetch.received[image_uid] = metadata.get("SeriesInstanceUID")
                        fetch.missing_images.pop(image_uid, None)
                        fetch.last_image_at = time.monotonic()
                except Exception as err:
                    fetch.receiving_errors.append(err)
                finally:
                    await async_os.remove(filename)

                # Subscribed until the fetch ends, as images of the study the PACS still sends
                # keep the C-MOVE alive (see send_c_move's last_activity)
                return False

            def handle_synced(token: str):
                # The snapshot comes first, as the main thread acts as soon as it sees the token.
                # The confirmed replay of the receiver precedes any C-MOVE, so images missing
                # then are still to come.
                if token != REPLAY_SYNC_TOKEN:
                    fetch.missing_at_sync.clear()
                    fetch.missing_at_sync.update(fetch.missing_images)
                fetch.synced_tokens.add(token)

            subscribe_task = asyncio.create_task(
                file_transmit.subscribe(
                    study_uid,
                    handle_received_file,
                    subscribed_handler=fetch.subscribed.set,
                    synced_handler=handle_synced,
                )
            )

            while True:
                await asyncio.sleep(0.1)

                # Not sent once the subscription ended, as then nothing is missing anymore or
                # the broken connection is reported below
                while not fetch.sync_requests.empty():
                    await file_transmit.request_sync(fetch.sync_requests.get())

                if fetch.stop_consumer.is_set():
                    subscribe_task.cancel()
                    break

                if subscribe_task.done():
                    if err := subscribe_task.exception():
                        error = RetriableDicomError("Connection to the DICOM receiver failed.")
                        error.__cause__ = err
                        fetch.receiving_errors.append(error)
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
