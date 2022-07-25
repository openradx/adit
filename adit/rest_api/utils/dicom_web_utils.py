from requests import RequestException
from pathlib import Path
import logging
import errno

from rest_framework.views import APIView
from rest_framework.exceptions import NotAcceptable

from adit.core.models import DicomServer
from adit.core.utils.dicom_connector import (
    DicomConnector, 
    sanitize_dirname, 
    connect_to_server,
    _evaluate_get_move_results, 
    _check_required_id,
    _make_query_dataset, 
)

from pynetdicom import evt

# pylint: disable=no-name-in-module
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
)

from adit.core.errors import RetriableTaskError


logger = logging.getLogger(__name__)



class DicomWebAPIView(APIView):
    MODE = None
    query = None

    def handle_request(self, request, accept_header=False, *args, **kwargs):
        # Find PACS and connect
        pacs_ae_title = kwargs.get("pacs", None)
        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)
        if len(SourceServerSet) != 1:
            raise RequestException(f"The specified PACS with AE title: {pacs_ae_title} does not exist or multiple Entities with this title exist.")
        SourceServer = SourceServerSet[0]

        # update query
        query = self.query.copy()
        query.update(request.query_params.copy())

        StudyInstanceUID = kwargs.get("StudyInstanceUID")
        if self.LEVEL == "SERIES" and StudyInstanceUID is None:
            raise NotImplementedError("Query for series without specified study is not yet supported.")
        SeriesInstanceUID = kwargs.get("SeriesInstanceUID")
        if not StudyInstanceUID is None:
            query["StudyInstanceUID"] = StudyInstanceUID
        if not SeriesInstanceUID is None:
            query["SeriesInstanceUID"] = StudyInstanceUID
        
        if accept_header:
            format = self.handle_accept_header(request, *args, **kwargs)
            return SourceServer, query, format

        return SourceServer, query


    def handle_accept_header(self, request, *args, **kwargs):
        if kwargs.get("mode") == "metadata":
            mode = "meta"
            supported_file_formats = self.Serializer.META_DATA_FORMATS
            default_file_format = self.Serializer.META_DATA_D_FORMAT
        else:
            mode = "bulk"
            supported_file_formats = self.Serializer.FILE_FORMATS
            default_file_format = self.Serializer.FILE_D_FORMAT
        
        accept_headers = self._format_accept_header(request.META["HTTP_ACCEPT"])
        for header in accept_headers:
            if header["media_type"] in self.Serializer.MULTIPART_MEDIA_TYPES:
                if header["type"] in supported_file_formats and header["type"] in self.Serializer.MULTIPART_FORMATS:
                    file_format = header["type"]
                    if not header.get("boundary") is None:
                        self.Serializer.BOUNDARY = header["boundary"]
            elif header["media_type"] in self.Serializer.MEDIA_TYPES:
                file_format = header["media_type"]
            elif header["media_type"] == "*/*":
                file_format = default_file_format

        if file_format is None:
            raise NotAcceptable()
        
        logger.debug(f"Accepted file format: {file_format} for retrieve mode: {mode}.")

        format = {
            "mode": mode,
            "file_format": file_format,
        }

        return format

                    
    def _format_accept_header(self, accept_header_str):
        chars_to_remove = [" ", "'", '"']
        for char in chars_to_remove:
            accept_header_str = accept_header_str.replace(char, "")
        accept_headers = [header.split(";") for header in accept_header_str.split(",")]
        accept_headers_formated = [{} for i in range(len(accept_headers))]
        for j in range(len(accept_headers)):
            accept_header = accept_headers[j]
            accept_headers_formated[j]["media_type"] = accept_header[0]
            for i in range(1, len(accept_header)):
                key, value = accept_header[i].split("=")
                accept_headers_formated[j][key] = value
        
        return accept_headers_formated



class DicomWebConnector(DicomConnector):
    def retrieve_study(
        self, 
        study_uid, 
        series_list,
        format,
        folder_path,
        serializer,
        patient_id = "",
        modality = None,
        modifier_callback = None,
    ):
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            multipart_folder_path = self.retrieve_series(
                study_uid, series_uid, format, folder_path, serializer, modifier_callback=modifier_callback
            )
        
        logger.debug("Successfully downloaded study %s to ADIT.", study_uid)
        
    
    def retrieve_series(
        self,
        study_uid,
        series_uid,
        format,
        folder_path,
        serializer,
        patient_id = "",
        modality=None,
        modifier_callback=None,
    ):

        query = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }
 
        if self.server.patient_root_get_support or self.server.study_root_get_support:
            self._retrieve_series_get(query, format, folder_path, serializer, modifier_callback)
            logger.debug(
                "Successfully downloaded series %s of study %s.", series_uid, study_uid
            )
        else:
            raise ValueError(
                "No Query/Retrieve Information Model supported to download images."
            )

        return folder_path

    def _retrieve_series_get(self, query, format, folder_path, serializer, modifier_callback=None):
        results = self._send_c_get_retrieve(query, format, folder_path, serializer, modifier_callback)

        _evaluate_get_move_results(results, query)


    @connect_to_server("get")
    def _send_c_get_retrieve(  # pylint: disable=too-many-arguments
        self, query_dict, format, folder_path, serializer, callback=None, msg_id=1
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
            evt.EVT_C_STORE, _handle_c_get_retrieve, [format, folder_path, serializer, callback, store_errors]
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

def _handle_c_get_retrieve(event, format, folder_path, serializer, modifier_callback, errors):
    """Handle a C-STORE request event."""
    mode, file_format = format["mode"], format["file_format"]

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

    file_path = folder_path / "multipart.txt"

    try:
        serializer.write(
            serializer,
            ds,
            file_path,
            file_format = file_format,
        )
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