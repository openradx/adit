import inspect
import logging
import time
from contextlib import contextmanager
from functools import wraps
from http import HTTPStatus
from os import PathLike
from pathlib import Path
from typing import Callable, Iterator, NoReturn

from dicomweb_client import DICOMwebClient
from pydicom import Dataset
from pydicom.errors import InvalidDicomError
from requests import HTTPError

from ..errors import DicomError, RetriableDicomError, is_retriable_http_status
from ..metrics import DICOM_OPERATION_COUNTER, DICOM_OPERATION_DURATION
from ..models import DicomServer
from ..types import DicomLogEntry
from ..utils.dicom_dataset import QueryDataset, ResultDataset
from ..utils.dicom_utils import read_dataset
from ..utils.retry_config import (
    retry_dicomweb_retrieve,
    retry_dicomweb_search,
    retry_dicomweb_store,
)

logger = logging.getLogger(__name__)

Modifier = Callable[[Dataset], None]


@contextmanager
def track_dicomweb_operation(operation: str, server_ae_title: str):
    """Context manager to track DICOMweb operation metrics."""
    start_time = time.time()
    status = "success"
    try:
        yield
    except Exception:
        status = "failure"
        raise
    finally:
        duration = time.time() - start_time
        DICOM_OPERATION_COUNTER.labels(
            operation=operation, server=server_ae_title, status=status
        ).inc()
        DICOM_OPERATION_DURATION.labels(operation=operation, server=server_ae_title).observe(
            duration
        )


def connect_to_server():
    """
    Creates a DICOMwebClient instance and makes it available as
    `self.dicomweb_client` in the decorated method.
    """

    def decorator(func):
        def setup_dicomweb_client(self: "DicomWebConnector") -> None:
            logger.debug("Setting up DICOMweb client with url %s", self.server.dicomweb_root_url)

            if not self.server.dicomweb_root_url:
                raise DicomError("Missing DICOMweb root url.")

            headers = {}
            if self.server.dicomweb_authorization_header:
                headers["Authorization"] = self.server.dicomweb_authorization_header

            self.dicomweb_client = DICOMwebClient(
                url=self.server.dicomweb_root_url,
                qido_url_prefix=(
                    self.server.dicomweb_qido_prefix if self.server.dicomweb_qido_prefix else None
                ),
                wado_url_prefix=(
                    self.server.dicomweb_wado_prefix if self.server.dicomweb_wado_prefix else None
                ),
                stow_url_prefix=(
                    self.server.dicomweb_stow_prefix if self.server.dicomweb_stow_prefix else None
                ),
                headers=headers,
            )

        @wraps(func)
        def gen_wrapper(self: "DicomWebConnector", *args, **kwargs):
            setup_dicomweb_client(self)
            yield from func(self, *args, **kwargs)
            self.dicomweb_client = None

        @wraps(func)
        def func_wrapper(self: "DicomWebConnector", *args, **kwargs):
            setup_dicomweb_client(self)
            result = func(self, *args, **kwargs)
            self.dicomweb_client = None
            return result

        return gen_wrapper if inspect.isgeneratorfunction(func) else func_wrapper

    return decorator


class DicomWebConnector:
    dicomweb_client: DICOMwebClient | None = None

    def __init__(
        self,
        server: DicomServer,
    ) -> None:
        self.server = server

        # TODO: log warnings
        self.logs: list[DicomLogEntry] = []

    def abort(self) -> None:
        """
        Abort all running DICOMweb operations.
        """
        if self.dicomweb_client and self.dicomweb_client._session:
            self.dicomweb_client._session.close()

    @retry_dicomweb_search
    @connect_to_server()
    def send_qido_rs(
        self, query: QueryDataset, limit_results: int | None = None
    ) -> list[ResultDataset]:
        logger.debug("Sending QIDO-RS with query: %s", query)

        search_filters, fields = query.get_search_filters_and_fields()

        level = search_filters.pop("QueryRetrieveLevel", "")
        if not level:
            raise DicomError("Missing QueryRetrieveLevel.")

        if not self.server.dicomweb_qido_support:
            raise DicomError("DICOMweb QIDO-RS is not supported by the server.")

        assert self.dicomweb_client

        with track_dicomweb_operation("QIDO-RS", self.server.ae_title):
            try:
                if level == "STUDY":
                    results = self.dicomweb_client.search_for_studies(
                        fields=fields, search_filters=search_filters, limit=limit_results
                    )
                elif level == "SERIES":
                    study_uid = search_filters.pop("StudyInstanceUID", None)
                    results = self.dicomweb_client.search_for_series(
                        study_uid, fields=fields, search_filters=search_filters, limit=limit_results
                    )
                elif level == "IMAGE":
                    study_uid = search_filters.pop("StudyInstanceUID", None)
                    series_uid = search_filters.pop("SeriesInstanceUID", None)
                    results = self.dicomweb_client.search_for_instances(
                        study_uid,
                        series_uid,
                        fields=fields,
                        search_filters=search_filters,
                        limit=limit_results,
                    )
                else:
                    raise ValueError(f"Invalid QueryRetrieveLevel: {level}")

                return [ResultDataset(Dataset.from_json(result)) for result in results]
            except HTTPError as err:
                _handle_dicomweb_error(err, "QIDO-RS")

    @retry_dicomweb_retrieve
    @connect_to_server()
    def send_wado_rs(self, query: QueryDataset) -> Iterator[Dataset]:
        logger.debug("Sending WADO-RS with query: %s", query)

        query_dict = query.dictify()

        level = query_dict.pop("QueryRetrieveLevel", "")
        if not level:
            raise DicomError("Missing QueryRetrieveLevel.")

        if not self.server.dicomweb_wado_support:
            raise DicomError("DICOMweb WADO-RS is not supported by the server.")

        assert self.dicomweb_client

        with track_dicomweb_operation("WADO-RS", self.server.ae_title):
            try:
                if level == "STUDY":
                    study_uid = query_dict.pop("StudyInstanceUID", "")
                    if not study_uid:
                        raise DicomError("Missing StudyInstanceUID for WADO-RS on study level.")
                    yield from self.dicomweb_client.iter_study(study_uid)
                elif level == "SERIES":
                    study_uid = query_dict.pop("StudyInstanceUID", "")
                    series_uid = query_dict.pop("SeriesInstanceUID", "")
                    if not study_uid:
                        raise DicomError("Missing StudyInstanceUID for WADO-RS on series level.")
                    if not series_uid:
                        raise DicomError("Missing SeriesInstanceUID for WADO-RS on series level.")
                    yield from self.dicomweb_client.iter_series(study_uid, series_uid)
                elif level == "IMAGE":
                    study_uid = query_dict.pop("StudyInstanceUID", "")
                    series_uid = query_dict.pop("SeriesInstanceUID", "")
                    sop_instance_uid = query_dict.pop("SOPInstanceUID", "")
                    if not study_uid:
                        raise DicomError("Missing StudyInstanceUID for WADO-RS on image level.")
                    if not series_uid:
                        raise DicomError("Missing SeriesInstanceUID for WADO-RS on image level.")
                    if not sop_instance_uid:
                        raise DicomError("Missing SOPInstanceUID for WADO-RS on image level.")
                    yield self.dicomweb_client.retrieve_instance(
                        study_uid, series_uid, sop_instance_uid
                    )
                else:
                    raise DicomError(f"Invalid QueryRetrieveLevel: {level}")
            except HTTPError as err:
                _handle_dicomweb_error(err, "WADO-RS")

    @retry_dicomweb_store
    @connect_to_server()
    def send_stow_rs(
        self,
        resource: PathLike | list[Dataset],
        modifier: Modifier | None = None,
    ):
        retriable_failures: list[str] = []

        def _send_dataset(ds: Dataset) -> None:
            # Allow to manipulate the dataset by an optional modifier function
            if modifier:
                modifier(ds)

            assert self.dicomweb_client

            try:
                self.dicomweb_client.store_instances([ds])
            except HTTPError as err:
                assert err.response is not None
                status_code = err.response.status_code
                if is_retriable_http_status(status_code):
                    retriable_failures.append(ds.SOPInstanceUID)
                else:
                    _handle_dicomweb_error(err, "STOW-RS")

        if not self.server.dicomweb_stow_support:
            raise DicomError("DICOMweb STOW-RS is not supported by the server.")

        with track_dicomweb_operation("STOW-RS", self.server.ae_title):
            if isinstance(resource, list):  # resource is a list of datasets
                logger.debug("Sending STOW of %d datasets.", len(resource))

                for ds in resource:
                    logger.debug("Sending C-STORE of SOP instance %s.", str(ds.SOPInstanceUID))
                    _send_dataset(ds)
            else:  # resource is a path to a folder
                folder = Path(resource)
                if not folder.is_dir():
                    raise DicomError(f"Resource is not a valid folder: {resource}")

                logger.debug("Sending STOW of folder: %s", folder.absolute())

                invalid_dicoms: list[PathLike] = []
                for path in folder.rglob("*"):
                    if not path.is_file():
                        continue

                    try:
                        ds = read_dataset(path)
                    except InvalidDicomError as err:
                        logger.error("Failed to read DICOM file %s: %s", path, err)
                        invalid_dicoms.append(path)
                        continue  # Try to handle rest of the images and raise the error later

                    _send_dataset(ds)

                if invalid_dicoms:
                    raise DicomError(
                        f"{len(invalid_dicoms)} DICOM file{'s' if len(invalid_dicoms) > 1 else ''} "
                        " could not be read for STOW-RS."
                    )

            if retriable_failures:
                plural = len(retriable_failures) > 1
                raise RetriableDicomError(
                    f"{len(retriable_failures)} STOW-RS operation{'s' if plural else ''} failed."
                )


def _handle_dicomweb_error(err: HTTPError, op: str) -> NoReturn:
    """Handle DICOMweb HTTPError by converting to appropriate exception type.

    Args:
        err: The HTTPError that occurred
        op: Operation name (QIDO-RS, WADO-RS, STOW-RS) for error messages

    Raises:
        RetriableDicomError: If the error is transient and should be retried
        HTTPError: If the error is permanent and should not be retried
    """
    assert err.response is not None
    status_code = err.response.status_code
    status_phrase = HTTPStatus(status_code).phrase
    if is_retriable_http_status(status_code):
        raise RetriableDicomError(
            f"DICOMweb {op} request failed: {status_phrase} [{status_code}]."
        ) from err
    else:
        logger.exception(
            f"DICOMweb {op} request failed critically: {status_phrase} [{status_code}]."
        )
        raise err
