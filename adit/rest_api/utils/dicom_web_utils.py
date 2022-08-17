from pathlib import Path
import logging
import errno
from typing import Type

from adit.core.errors import RetriableTaskError
from adit.core.utils.dicom_connector import (
    DicomConnector, 
    connect_to_server,
    _evaluate_get_move_results, 
    _check_required_id,
    _make_query_dataset, 
)
from ..serializers import DicomWebSerializer

from pynetdicom import evt
from pynetdicom.events import Event
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
)


logger = logging.getLogger(__name__)


class DicomWebConnector(DicomConnector):
    def retrieve_series_list(
        self, 
        study_uid: str, 
        series_list: str,
        mode: str,
        content_type: str,
        folder_path: str,
        serializer: Type[DicomWebSerializer],
        modifier_callback = None,
    ) -> None:
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            multipart_folder_path = self.retrieve_series(
                study_uid, 
                series_uid, mode, 
                content_type, 
                folder_path, serializer, 
                modifier_callback=modifier_callback,
            )
        
        logger.debug("Successfully downloaded study %s to ADIT.", study_uid)
        
    
    def retrieve_series(
        self,
        study_uid: str,
        series_uid: str,
        mode: str,
        content_type: str,
        folder_path: str,
        serializer: Type[DicomWebSerializer],
        modifier_callback=None,
    ) -> str:

        query_dict = {
            "QueryRetrieveLevel": "SERIES",
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }
 
        if self.server.patient_root_get_support or self.server.study_root_get_support:
            self._retrieve_series_get(
                query_dict, 
                mode, 
                content_type, 
                folder_path, 
                serializer, 
                modifier_callback
            )

            logger.debug(
                "Successfully downloaded series %s of study %s.", series_uid, study_uid
            )
        else:
            raise ValueError(
                "No Query/Retrieve Information Model supported to download images."
            )

        return folder_path

    def _retrieve_series_get(
        self, 
        query_dict: dict, 
        mode: str, 
        content_type: str, 
        folder_path: str, 
        serializer: Type[DicomWebSerializer], 
        modifier_callback=None
    ) -> None:
        results = self._send_c_get_retrieve(
            query_dict, 
            mode, 
            content_type, 
            folder_path, 
            serializer, 
            modifier_callback
        )

        _evaluate_get_move_results(results, query_dict)


    @connect_to_server("get")
    def _send_c_get_retrieve(  # pylint: disable=too-many-arguments
        self, 
        query_dict: dict, 
        mode: str, 
        content_type: str, 
        folder_path: str, 
        serializer: Type[DicomWebSerializer], 
        callback=None, 
        msg_id=1
    ):
        logger.debug("Sending C-GET with query: %s", query_dict)

        # Transfer of only one study at a time is supported by ADIT
        patient_id = _check_required_id(query_dict.get("PatientID"))
        study_uid = _check_required_id(query_dict.get("StudyInstanceUID"))

        if self.server.study_root_get_support and study_uid:
            query_model = StudyRootQueryRetrieveInformationModelGet
        elif self.server.patient_root_get_support and patient_id and study_uid:
            query_model = PatientRootQueryRetrieveInformationModelGet
        else:
            raise ValueError(
                "No valid Query/Retrieve Information Model for C-GET could be selected."
            )

        query_ds = _make_query_dataset(query_dict)
        store_errors = []
        self.assoc.bind(
            evt.EVT_C_STORE, _handle_c_get_retrieve, [mode, content_type, folder_path, serializer, callback, store_errors]
        )

        try:
            responses = self.assoc.send_c_get(query_ds, query_model, msg_id)
            results = self._fetch_results(responses, "C-GET", query_dict)
        except Exception as err:
            # Check if an error was triggered by our own store handler due to
            # aborting the assocation.
            if store_errors:
                raise store_errors[0]

            # If not just raise the original error.
            raise err
        finally:
            self.assoc.unbind(evt.EVT_C_STORE, _handle_c_get_retrieve)

        return results

def _handle_c_get_retrieve(
    event: Type[Event], 
    mode: str, 
    content_type: str, 
    folder_path: str, 
    serializer: Type[DicomWebSerializer], 
    modifier_callback, 
    errors
):
    """Handle a C-STORE request event."""
    ds = event.dataset
    context = event.context

    # Add DICOM File Meta Information
    ds.file_meta = event.file_meta

    # Set the transfer syntax attributes of the dataset
    ds.is_little_endian = context.transfer_syntax.is_little_endian
    ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

    folder_path = Path(folder_path)
    folder_path.mkdir(parents=True, exist_ok=True)

    # Allow to manipuate the dataset by using a callback before saving to disk
    if modifier_callback:
        modifier_callback(ds)

    file_path = folder_path / "response.txt"

    try:
        serializer.write(ds)
    except OSError as err:
        if err.errno == errno.ENOSPC:
            # No space left on destination
            logger.exception("Out of disk space while saving %s.", file_path)
            no_space_error = RetriableTaskError(
                "Out of disk space on destination.", long_delay=True
            )
            no_space_error.__cause__ = err
            errors.append(no_space_error)
    
            # Unfortunately not all PACS servers support or respect a C-CANCEL request,
            # so we just abort the association.
            # See https://github.com/pydicom/pynetdicom/issues/553
            # and https://groups.google.com/g/orthanc-users/c/tS826iEzHb0
            event.assoc.abort()
    
            # Answert with "Out of Resources"
            # see https://pydicom.github.io/pynetdicom/stable/service_classes/defined_procedure_service_class.html
            return 0xA702

    # Return a 'Success' status
    return 0x0000