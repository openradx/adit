import inspect
import logging
import time
from functools import wraps
from os import PathLike
from pathlib import Path
from typing import Callable, Iterator, Literal

from django.conf import settings
from pydicom import Dataset
from pydicom.errors import InvalidDicomError
from pynetdicom import debug_logger
from pynetdicom._globals import STATUS_FAILURE, STATUS_PENDING, STATUS_SUCCESS, STATUS_WARNING
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.association import Association
from pynetdicom.events import EVT_C_STORE, Event
from pynetdicom.presentation import (
    BasicWorklistManagementPresentationContexts,
    QueryRetrievePresentationContexts,
    UnifiedProcedurePresentationContexts,
    build_role,
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,  # pyright: ignore
    PatientRootQueryRetrieveInformationModelGet,  # pyright: ignore
    PatientRootQueryRetrieveInformationModelMove,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelFind,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelGet,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelMove,  # pyright: ignore
)
from pynetdicom.status import code_to_category

from ..errors import DicomError, RetriableDicomError
from ..models import DicomServer
from ..types import DicomLogEntry
from ..utils.dicom_dataset import QueryDataset, ResultDataset
from ..utils.dicom_utils import has_wildcards, read_dataset
from ..utils.presentation_contexts import StoragePresentationContexts

logger = logging.getLogger(__name__)

DimseService = Literal["C-FIND", "C-GET", "C-MOVE", "C-STORE"]

Modifier = Callable[[Dataset], None]


def connect_to_server(service: DimseService):
    """Automatically handles the connection when `auto_config` option is set.

    TODO: Think about using a context manager instead of a decorator.
    """

    def decorator(func):
        @wraps(func)
        def gen_wrapper(self: "DimseConnector", *args, **kwargs):
            opened_connection = False

            is_connected = self.assoc and self.assoc.is_alive()
            if self.auto_connect and not is_connected:
                self.open_connection(service)
                opened_connection = True

            try:
                yield from func(self, *args, **kwargs)
            except Exception as err:
                self.abort_connection()
                raise err

            if opened_connection and self.auto_connect:
                self.close_connection()
                opened_connection = False

        @wraps(func)
        def func_wrapper(self: "DimseConnector", *args, **kwargs):
            opened_connection = False

            is_connected = self.assoc and self.assoc.is_alive()
            if self.auto_connect and not is_connected:
                self.open_connection(service)
                opened_connection = True

            try:
                result = func(self, *args, **kwargs)
            except Exception as err:
                self.abort_connection()
                raise err

            if opened_connection and self.auto_connect:
                self.close_connection()
                opened_connection = False

            return result

        return gen_wrapper if inspect.isgeneratorfunction(func) else func_wrapper

    return decorator


class DimseConnector:
    assoc: Association | None = None

    def __init__(
        self,
        server: DicomServer,
        auto_connect: bool = True,
        connection_retries: int = 2,
        retry_timeout: int = 30,  # in seconds
        acse_timeout: int | None = 60,
        connection_timeout: int | None = None,
        dimse_timeout: int | None = 60,
        network_timeout: int | None = 120,
    ) -> None:
        self.server = server
        self.auto_connect = auto_connect
        self.connection_retries = connection_retries
        self.retry_timeout = retry_timeout
        self.acse_timeout = acse_timeout
        self.connection_timeout = connection_timeout
        self.dimse_timeout = dimse_timeout
        self.network_timeout = network_timeout
        self.logs: list[DicomLogEntry] = []

        if settings.ENABLE_DICOM_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

    def open_connection(self, service: DimseService):
        if self.assoc:
            raise AssertionError("A former connection was not closed properly.")

        logger.debug("Opening connection to DICOM server %s.", self.server.ae_title)

        for i in range(self.connection_retries + 1):
            try:
                self._associate(service)
                break
            except ConnectionError as err:
                logger.exception("Could not connect to %s.", self.server)
                if i < self.connection_retries:
                    logger.info(
                        "Retrying to connect in %d seconds.",
                        self.retry_timeout,
                    )
                    time.sleep(self.retry_timeout)
                else:
                    raise err

    def _associate(self, service: DimseService):
        ae = AE(settings.CALLING_AE_TITLE)

        # Speed up by reducing the number of required DIMSE messages
        # https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
        ae.maximum_pdu_size = 0

        # We only use the timeouts if set, otherwise we leave the default timeouts
        # https://github.com/pydicom/pynetdicom/blob/4972781323e4f726e99ed03cf6ddce786f90f486/pynetdicom/ae.py#L96
        if self.acse_timeout is not None:
            ae.acse_timeout = self.acse_timeout
        if self.connection_timeout is not None:
            ae.connection_timeout = self.connection_timeout
        if self.dimse_timeout is not None:
            ae.dimse_timeout = self.dimse_timeout
        if self.network_timeout is not None:
            ae.network_timeout = self.network_timeout

        # Setup the contexts
        # (inspired by https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/apps)
        ext_neg = []
        if service == "C-FIND":
            ae.requested_contexts = (
                QueryRetrievePresentationContexts
                + BasicWorklistManagementPresentationContexts
                + UnifiedProcedurePresentationContexts
            )
        elif service == "C-GET":
            # The maximum requested contexts is 128. StoragePresentationContexts currently
            # contains 120 storage contexts. So even with the query/retrieve contexts added we
            # should have no problem.
            ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
            ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
            for cx in StoragePresentationContexts:
                assert cx.abstract_syntax is not None
                ae.add_requested_context(cx.abstract_syntax)
                ext_neg.append(build_role(cx.abstract_syntax, scp_role=True))
        elif service == "C-MOVE":
            ae.requested_contexts = QueryRetrievePresentationContexts
        elif service == "C-STORE":
            ae.requested_contexts = StoragePresentationContexts
        else:
            raise DicomError(f"Invalid DIMSE service: {service}")

        self.assoc = ae.associate(
            self.server.host,
            self.server.port,
            ae_title=self.server.ae_title,
            ext_neg=ext_neg,
        )

        if not self.assoc.is_established:
            raise RetriableDicomError(f"Could not connect to {self.server}.")

    def close_connection(self):
        logger.debug("Closing connection to DICOM server %s.", self.server.ae_title)

        assert self.assoc
        self.assoc.release()
        self.assoc = None

    def abort_connection(self):
        if self.assoc:
            logger.debug("Aborting connection to DICOM server %s.", self.server.ae_title)
            self.assoc.abort()

    @connect_to_server("C-FIND")
    def send_c_find(
        self, query: QueryDataset, limit_results: int | None = None, msg_id: int = 1
    ) -> Iterator[ResultDataset]:
        logger.debug("Sending C-FIND with query:\n%s", query)

        level: str | None = query.get("QueryRetrieveLevel")
        if not level:
            raise DicomError("Missing QueryRetrieveLevel for C-FIND query.")

        patient_id = query.get("PatientID", "")
        has_valid_patient_id = bool(patient_id) and not has_wildcards(patient_id)

        if self.server.study_root_find_support and level != "PATIENT":
            query_model = StudyRootQueryRetrieveInformationModelFind
        elif self.server.patient_root_find_support and (level == "PATIENT" or has_valid_patient_id):
            query_model = PatientRootQueryRetrieveInformationModelFind
        else:
            raise DicomError("No valid Query/Retrieve Information Model for C-FIND could be found.")

        assert self.assoc and self.assoc.is_alive()
        responses = self.assoc.send_c_find(query.dataset, query_model, msg_id)

        result_counter = 0
        for status, identifier in responses:
            if not status:
                raise RetriableDicomError(
                    "Connection timed out, was aborted or received invalid response."
                )

            status_category = code_to_category(status.Status)
            if status_category == STATUS_SUCCESS:
                logger.debug("C-FIND completed successfully.")
                break

            elif status_category == STATUS_PENDING:
                if not identifier:
                    raise RetriableDicomError("Missing identifier for pending C-FIND.")

                yield ResultDataset(identifier)

                result_counter += 1
                if result_counter == limit_results:
                    self.abort_connection()
                    break

            else:
                raise RetriableDicomError(
                    f"Unexpected error during C-FIND [{status_category}]:\n{status}"
                )

    @connect_to_server("C-GET")
    def send_c_get(
        self,
        query: QueryDataset,
        store_handler: Callable[[Event, list[Exception]], int],
        store_errors: list[Exception],
        msg_id: int = 1,
    ) -> None:
        logger.debug("Sending C-GET with query:\n%s", query)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = query.get("PatientID", "")
        has_patient_id = bool(patient_id) and not has_wildcards(patient_id)
        study_uid = query.get("StudyInstanceUID", "")
        has_study_uid = bool(study_uid) and not has_wildcards(study_uid)

        if self.server.study_root_get_support and has_study_uid:
            query_model = StudyRootQueryRetrieveInformationModelGet
        elif self.server.patient_root_get_support and has_patient_id and has_study_uid:
            query_model = PatientRootQueryRetrieveInformationModelGet
        else:
            raise DicomError(
                "No valid Query/Retrieve Information Model for C-GET could be selected."
            )

        assert self.assoc and self.assoc.is_alive()
        self.assoc.bind(EVT_C_STORE, store_handler, [store_errors])

        responses = self.assoc.send_c_get(query.dataset, query_model, msg_id)

        self._handle_get_and_move_responses(responses, "C-GET")

    @connect_to_server("C-MOVE")
    def send_c_move(self, query: QueryDataset, dest_aet: str, msg_id: int = 1) -> None:
        logger.debug("Sending C-MOVE with query:\n%s", query)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = query.get("PatientID", "")
        has_patient_id = bool(patient_id) and not has_wildcards(patient_id)
        study_uid = query.get("StudyInstanceUID", "")
        has_study_uid = bool(study_uid) and not has_wildcards(study_uid)

        if self.server.study_root_move_support and has_study_uid:
            query_model = StudyRootQueryRetrieveInformationModelMove
        elif self.server.patient_root_move_support and has_patient_id and has_study_uid:
            query_model = PatientRootQueryRetrieveInformationModelMove
        else:
            raise DicomError(
                "No valid Query/Retrieve Information Model for C-MOVE could be selected."
            )

        assert self.assoc and self.assoc.is_alive()
        responses = self.assoc.send_c_move(query.dataset, dest_aet, query_model, msg_id)

        self._handle_get_and_move_responses(responses, "C-MOVE")

    @connect_to_server("C-STORE")
    def send_c_store(
        self, resource: PathLike | list[Dataset], modifier: Modifier | None = None, msg_id: int = 1
    ) -> None:
        warnings: list[str] = []
        failures: list[str] = []

        def _send_dataset(ds: Dataset) -> None:
            # Allow to manipulate the dataset by an optional modifier function
            if modifier:
                modifier(ds)

            assert self.assoc and self.assoc.is_alive()
            status = self.assoc.send_c_store(ds, msg_id)

            if not status:
                raise RetriableDicomError(
                    "Connection timed out, was aborted or received invalid response."
                )
            else:
                status_category = code_to_category(status.Status)
                if status_category == STATUS_WARNING:
                    warnings.append(ds.StudyInstanceUID)
                    logger.warning(f"Warning during C-STORE [{status_category}]:\n{status}")
                elif status_category != STATUS_SUCCESS:
                    failures.append(ds.StudyInstanceUID)
                    logger.error(f"Unexpected error during C-STORE [{status_category}]:\n{status}")

        if not self.server.store_scp_support:
            raise DicomError("C-STORE operation not supported by server.")

        if isinstance(resource, list):  # resource is a list of datasets
            logger.debug("Sending C-STORE of %d datasets.", len(resource))

            for ds in resource:
                logger.debug("Sending C-STORE of SOP instance %s.", str(ds.SOPInstanceUID))
                _send_dataset(ds)
        else:  # resource is a folder
            folder = Path(resource)
            if not folder.is_dir():
                raise DicomError(f"Resource is not a valid folder: {resource}.")

            logger.debug("Sending C-STORE of folder: %s", folder.absolute())

            invalid_dicoms: list[PathLike] = []
            for path in folder.rglob("*"):
                if not path.is_file():
                    continue

                try:
                    ds = read_dataset(path)
                except InvalidDicomError as err:
                    logger.error("Failed to read DICOM file %s: %s", path, err)
                    invalid_dicoms.append(path)
                    continue  # We try to handle the rest of the images and raise the error later

                _send_dataset(ds)

            if invalid_dicoms:
                raise DicomError(
                    f"{len(invalid_dicoms)} DICOM file{'s' if len(invalid_dicoms) > 1 else ''} "
                    " could not be read for C-STORE."
                )

        if warnings:
            # TODO: Maybe raise a warning or somehow else inform that the task has warnings
            pass

        if failures:
            plural = len(failures) > 1
            raise RetriableDicomError(
                f"{len(failures)} C-STORE operation{'s' if plural else ''} failed."
            )

    def _handle_get_and_move_responses(
        self, responses: Iterator[tuple[Dataset, Dataset | None]], op: Literal["C-GET", "C-MOVE"]
    ) -> None:
        for status, identifier in responses:
            if not status:
                raise RetriableDicomError(
                    "Connection timed out, was aborted or received invalid response."
                )

            status_category = code_to_category(status.Status)

            logger.debug(f"Received {op} status response [{status_category}]:\n{status}")

            if status_category in [STATUS_SUCCESS, STATUS_WARNING]:
                # Optional operation primitive parameters
                # https://pydicom.github.io/pynetdicom/dev/reference/generated/pynetdicom.dimse_primitives.C_GET.html
                # https://pydicom.github.io/pynetdicom/dev/reference/generated/pynetdicom.dimse_primitives.C_MOVE.html
                completed_suboperations: int | None = status.get("NumberOfCompletedSuboperations")
                failed_suboperations: int | None = status.get("NumberOfFailedSuboperations")
                warning_suboperations: int | None = status.get("NumberOfWarningSuboperations")

                if failed_suboperations or warning_suboperations:
                    # On some PACS (GE and Synapse) we get a SUCCESS response even when all
                    # sub-operations failed.
                    # https://github.com/pydicom/pynetdicom/issues/552
                    if failed_suboperations and not completed_suboperations:
                        raise RetriableDicomError("All sub-operations failed.")

                    if failed_suboperations and completed_suboperations:
                        message = f"{failed_suboperations} sub-operations failed:\n{status}"
                        self.logs.append(
                            {
                                "level": "Warning",
                                "title": "Some failed sub-operations",
                                "message": message,
                            }
                        )
                        logger.warn(message)

                    if warning_suboperations:
                        message = f"{warning_suboperations} sub-operations with warnings."
                        self.logs.append(
                            {
                                "level": "Warning",
                                "title": "Sub-operations with warnings",
                                "message": message,
                            }
                        )
                        logger.warn(message)
                else:
                    if status_category == STATUS_WARNING:
                        message = f"Unknown warning:\n{status}"
                        self.logs.append(
                            {
                                "level": "Warning",
                                "title": "Unexpected warnings",
                                "message": message,
                            }
                        )
                        logger.warn(message)

            if status_category == STATUS_FAILURE:
                if identifier:
                    failed_image_uids = identifier.get("FailedSOPInstanceUIDList", [])
                    if failed_image_uids:
                        if isinstance(failed_image_uids, str):
                            failed_image_uids = [failed_image_uids]
                        logger.error(
                            "Erroneous images (SOPInstanceUID): %s", ", ".join(failed_image_uids)
                        )
                        raise RetriableDicomError(
                            f"Failed to transfer several images with {op} [{status_category}]:\n"
                            f"{status}"
                        )
                raise RetriableDicomError(
                    f"Unexpected error during {op} [{status_category}]:\n{status}"
                )
