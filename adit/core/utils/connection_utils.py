import logging
import time
from typing import Literal

from dicomweb_client import DICOMwebClient
from django.conf import settings
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.association import Association
from pynetdicom.presentation import (
    BasicWorklistManagementPresentationContexts,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
    build_role,
)
from pynetdicom.sop_class import (
    EncapsulatedMTLStorage,  # pyright: ignore
    EncapsulatedOBJStorage,  # pyright: ignore
    EncapsulatedSTLStorage,  # pyright: ignore
    PatientRootQueryRetrieveInformationModelGet,  # pyright: ignore
    StudyRootQueryRetrieveInformationModelGet,  # pyright: ignore
)

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer

logger = logging.getLogger(__name__)

DimseService = Literal["C-FIND", "C-GET", "C-MOVE", "C-STORE"]


class create_association:
    def __init__(
        self,
        server: DicomServer,
        service: DimseService,
        connection_retries: int = 2,
        retry_timeout: int = 30,  # in seconds
        acse_timeout: int | None = 60,
        connection_timeout: int | None = None,
        dimse_timeout: int | None = 60,
        network_timeout: int | None = 120,
    ) -> None:
        self.server = server
        self.service = service
        self.connection_retries = connection_retries
        self.retry_timeout = retry_timeout
        self.acse_timeout = acse_timeout
        self.connection_timeout = connection_timeout
        self.dimse_timeout = dimse_timeout
        self.network_timeout = network_timeout

        self.association: Association | None = None

    def __enter__(self) -> Association:
        self.association = self._open_association()
        return self.association

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._close_association()

    def _open_association(self) -> Association:
        logger.debug("Opening connection to DICOM server %s.", self.server.ae_title)

        association: Association
        for i in range(self.connection_retries + 1):
            try:
                association = self._associate()
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

        assert association
        return association

    def _associate(self) -> Association:
        ae = AE(settings.RECEIVER_AE_TITLE)

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
        if self.service == "C-FIND":
            ae.requested_contexts = (
                QueryRetrievePresentationContexts + BasicWorklistManagementPresentationContexts
            )
        elif self.service == "C-GET":
            # We must exclude as many storage contexts as query/retrieve contexts we add
            # because the maximum requested contexts is 128. "StoragePresentationContexts" is a list
            # that contains 128 storage contexts itself.
            exclude = [
                EncapsulatedSTLStorage,
                EncapsulatedOBJStorage,
                EncapsulatedMTLStorage,
            ]
            store_contexts = [
                cx for cx in StoragePresentationContexts if cx.abstract_syntax not in exclude
            ]
            ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
            ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
            for cx in store_contexts:
                assert cx.abstract_syntax is not None
                ae.add_requested_context(cx.abstract_syntax)
                ext_neg.append(build_role(cx.abstract_syntax, scp_role=True))
        elif self.service == "C-MOVE":
            ae.requested_contexts = QueryRetrievePresentationContexts
        elif self.service == "C-STORE":
            ae.requested_contexts = StoragePresentationContexts
        else:
            raise DicomError(f"Invalid DIMSE service: {self.service}")

        association = ae.associate(
            self.server.host,
            self.server.port,
            ae_title=self.server.ae_title,
            ext_neg=ext_neg,
        )

        if not association.is_established:
            raise RetriableDicomError(f"Could not connect to {self.server}.")

        return association

    def _close_association(self) -> None:
        logger.debug("Closing connection to DICOM server %s.", self.server.ae_title)

        assert self.association
        self.association.release()
        self.association = None


class create_dicomweb_client:
    def __init__(self, server: DicomServer) -> None:
        self.server = server

        self.dicomweb_client: DICOMwebClient | None = None

    def __enter__(self) -> DICOMwebClient:
        self.dicomweb_client = self._create_client()
        return self.dicomweb_client

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.dicomweb_client = None

    def _create_client(self) -> DICOMwebClient:
        logger.debug("Setting up DICOMweb client with url %s", self.server.dicomweb_root_url)

        if not self.server.dicomweb_root_url:
            raise DicomError("Missing DICOMweb root url.")

        headers = {}
        if self.server.dicomweb_authorization_header:
            headers["Authorization"] = self.server.dicomweb_authorization_header

        dicomweb_client = DICOMwebClient(
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

        return dicomweb_client
