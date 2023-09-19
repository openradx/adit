import logging
from http import HTTPStatus
from os import PathLike
from pathlib import Path
from typing import Callable, NoReturn

from dicomweb_client import DICOMwebClient
from pydicom import Dataset
from pydicom.errors import InvalidDicomError
from requests import HTTPError

from ..errors import DicomCommunicationError, DicomConnectionError
from ..models import DicomServer
from ..utils.dicom_dataset import QueryDataset, ResultDataset
from ..utils.dicom_utils import read_dataset

logger = logging.getLogger(__name__)

Modifier = Callable[[Dataset], None]


def connect_to_server():
    """
    Creates a DICOMwebClient instance and makes it available as
    `self.dicomweb_client` in the decorated method.
    """

    def decorator(func):
        def wrapper(self: "DicomWebConnector", *args, **kwargs):
            if not self.server.dicomweb_root_url:
                raise ValueError("Missing DICOMweb root url.")

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

            logger.debug("Set up dicomweb client with url %s", self.server.dicomweb_root_url)

            result = func(self, *args, **kwargs)

            self.dicomweb_client = None

            return result

        return wrapper

    return decorator


class DicomWebConnector:
    dicomweb_client: DICOMwebClient | None = None

    def __init__(self, server: DicomServer) -> None:
        self.server = server

    def abort(self) -> None:
        """
        Abort all running DICOMweb operations.
        """
        if self.dicomweb_client and self.dicomweb_client._session:
            self.dicomweb_client._session.close()

    # TODO: How about fields
    @connect_to_server()
    def send_qido_rs(
        self, query: QueryDataset, limit_results: int | None = None
    ) -> list[ResultDataset]:
        logger.debug("Sending QIDO-RS with query: %s", query)

        query_dict = query.dictify()

        level = query_dict.pop("QueryRetrieveLevel", "")
        if not level:
            raise ValueError("Missing QueryRetrieveLevel.")

        if not self.dicomweb_client:
            raise AssertionError("Missing DICOMweb client.")

        if not self.server.dicomweb_qido_support:
            raise ValueError("DICOMweb QIDO-RS is not supported by the server.")

        try:
            if level == "STUDY":
                results = self.dicomweb_client.search_for_studies(
                    search_filters=query_dict, limit=limit_results
                )
            elif level == "SERIES":
                study_uid = query_dict.pop("StudyInstanceUID", "")
                if study_uid:
                    results = self.dicomweb_client.search_for_series(
                        study_uid, search_filters=query_dict, limit=limit_results
                    )
                else:
                    results = self.dicomweb_client.search_for_series(
                        search_filters=query_dict, limit=limit_results
                    )
            else:
                raise ValueError(f"Invalid QueryRetrieveLevel: {level}")

            return [ResultDataset(Dataset.from_json(result)) for result in results]
        except HTTPError as err:
            _handle_dicomweb_error(err, "QIDO-RS")

    @connect_to_server()
    def send_wado_rs(self, query: QueryDataset) -> list[Dataset]:
        logger.debug("Sending WADO-RS with query: %s", query)

        # TODO: Do we really need the conversion?
        query_dict = query.dictify()

        level = query_dict.pop("QueryRetrieveLevel", "")
        if not level:
            raise ValueError("Missing QueryRetrieveLevel.")

        if not self.dicomweb_client:
            raise AssertionError("Missing DICOMweb client.")

        if not self.server.dicomweb_wado_support:
            raise ValueError("DICOMweb WADO-RS is not supported by the server.")

        try:
            if level == "STUDY":
                study_uid = query_dict.pop("StudyInstanceUID", "")
                if not study_uid:
                    raise ValueError("Missing StudyInstanceUID for WADO-RS on study level.")
                return self.dicomweb_client.retrieve_study(study_uid)
            elif level == "SERIES":
                study_uid = query_dict.pop("StudyInstanceUID", "")
                series_uid = query_dict.pop("SeriesInstanceUID", "")
                if not study_uid:
                    raise ValueError("Missing StudyInstanceUID for WADO-RS on series level.")
                if not series_uid:
                    raise ValueError("Missing SeriesInstanceUID for WADO-RS on series level.")
                return self.dicomweb_client.retrieve_series(study_uid, series_uid)
            else:
                raise ValueError(f"Invalid QueryRetrieveLevel: {level}")
        except HTTPError as err:
            _handle_dicomweb_error(err, "WADO-RS")

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

            if not self.dicomweb_client:
                raise AssertionError("Missing DICOMweb client.")

            try:
                self.dicomweb_client.store_instances([ds])
            except HTTPError as err:
                status_code = err.response.status_code
                if _is_retriable_error(status_code):
                    retriable_failures.append(ds.SOPInstanceUID)
                else:
                    _handle_dicomweb_error(err, "STOW-RS")

        if not self.server.dicomweb_stow_support:
            raise ValueError("DICOMweb STOW-RS is not supported by the server.")

        if isinstance(resource, list):  # resource is a list of datasets
            logger.debug("Sending STOW of %d datasets.", len(resource))

            for ds in resource:
                logger.debug("Sending C-STORE of SOP instance %s.", str(ds.SOPInstanceUID))
                _send_dataset(ds)
        else:  # resource is a path to a folder
            folder = Path(resource)
            if not folder.is_dir():
                raise ValueError(f"Resource is not a valid folder: {resource}")

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
                    continue  # We try to handle the rest of the instances and raise the error later

                _send_dataset(ds)

            if invalid_dicoms:
                raise IOError(
                    f"{len(invalid_dicoms)} DICOM file{'s' if len(invalid_dicoms) > 1 else ''} "
                    " could not be read for STOW-RS."
                )

        if retriable_failures:
            plural = len(retriable_failures) > 1
            raise DicomCommunicationError(
                f"{len(retriable_failures)} STOW-RS operation{'s' if plural else ''} failed."
            )


def _is_retriable_error(status_code: int) -> bool:
    retriable_status_codes = [408, 409, 429, 500, 503, 504]
    return status_code in retriable_status_codes


def _handle_dicomweb_error(err: HTTPError, op: str) -> NoReturn:
    status_code = err.response.status_code
    status_phrase = HTTPStatus(status_code).phrase
    if _is_retriable_error(status_code):
        raise DicomConnectionError(
            f"DICOMweb {op} request failed: {status_phrase} [{status_code}]."
        )
    else:
        logger.exception(
            f"DICOMweb {op} request failed critically: {status_phrase} [{status_code}]."
        )
        raise err
