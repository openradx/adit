import logging
import time
from pathlib import Path
import os
from dataclasses import dataclass
from pydicom.dataset import Dataset
from pydicom import dcmread
from pynetdicom import (
    AE,
    evt,
    build_role,
    debug_logger,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION,
)
from pynetdicom.sop_class import (  # pylint: disable-msg=no-name-in-module
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelMove,
)
from pynetdicom.status import code_to_category


def make_query_dataset(query_dict):
    """Turn a dict into a pydicom dataset for query."""

    ds = Dataset()
    for i in query_dict:
        setattr(ds, i, query_dict[i])
    return ds


def dictify_dataset(ds):
    """Turn a pydicom Dataset into a dict with keys derived from the Element tags."""

    output = dict()
    if ds:
        for elem in ds:
            # We only use non private tags as keywords may not be unique when
            # there are also private tags present.
            # See also https://github.com/pydicom/pydicom/issues/319
            if elem.tag.is_private:
                continue

            if elem.VR != "SQ":
                output[elem.keyword] = elem.value
            else:
                output[elem.keyword] = [dictify_dataset(item) for item in elem]
    return output


def connect_to_server(func):
    def wrapper(self, *args, **kwargs):
        if self.assoc is None or not self.assoc.is_alive():
            for i in range(self.config.connection_retries):
                try:
                    self.open()
                    break
                except ConnectionError as err:
                    logging.exception("Could not connect to server: %s", str(err))
                    if i < self.config.connection_retries - 1:
                        logging.info(
                            "Retrying to connect in %d seconds.",
                            self.config.retry_timeout,
                        )
                        time.sleep(self.config.retry_timeout)
                    else:
                        raise err

        result = None
        exception_occurred = False
        try:
            result = func(self, *args, **kwargs)
        except Exception as ex:  # pylint: disable=broad-except
            logging.exception(
                "An error occurred during DICOM operation %s: %s",
                func.__name__,
                str(ex),
            )
            exception_occurred = True
        finally:
            if exception_occurred or self.config.auto_close_connection:
                self.close()

        return result

    return wrapper


@dataclass
class DicomOperationConfig:  # pylint: disable=too-many-instance-attributes
    client_ae_title: str
    server_ae_title: str
    server_ip: str
    server_port: int
    patient_root_query_model: bool = True
    auto_close_connection: bool = True
    debug: bool = False
    connection_retries: int = 3
    retry_timeout: int = 30  # seconds


class DicomOperation:
    def __init__(self, config: DicomOperationConfig):
        self.config = config
        self.assoc = None

        if self.config.debug:
            debug_logger()

    def close(self):
        if self.assoc:
            self.assoc.release()
            self.assoc = None

    def send_c_echo(self):
        status = self.assoc.send_c_echo()
        results = [
            {
                "status": {
                    "code": status.Status,
                    "category": code_to_category(status.Status),
                },
                "data": {},
            }
        ]
        return results


class DicomFind(DicomOperation):
    def __init__(self, *args, **kwargs):
        super(DicomFind, self).__init__(*args, **kwargs)

        self.query_model = PatientRootQueryRetrieveInformationModelFind
        if not self.config.patient_root_query_model:
            self.query_model = StudyRootQueryRetrieveInformationModelFind

    # Open the association with the PACS server
    def open(self):
        ae = AE(ae_title=self.config.client_ae_title)
        ae.add_requested_context(self.query_model)
        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
        )

        if not self.assoc.is_established:
            raise ConnectionError(
                "Could not connect to DICOM server with AE Title %s."
                % self.config.server_ae_title
            )

    @connect_to_server
    def send_c_find(self, query_dict, msg_id=1):
        query_ds = make_query_dataset(query_dict)

        responses = self.assoc.send_c_find(query_ds, self.query_model, msg_id)

        results = []
        for status, ds in responses:
            if status:
                # TODO check if this is more appropriate
                # status_dict = self.dictify(status)
                # status_dict['status_category'] = code_to_category(status.Status)
                # query_response['status'].append(status_dict)

                results.append(
                    {
                        "status": {
                            "code": status.Status,
                            "category": code_to_category(status.Status),
                        },
                        "data": dictify_dataset(ds),
                    }
                )
            else:
                logging.error(
                    "Invalid connection during C-Find with query: %s", str(query_dict)
                )

        return results


class DicomGet(DicomOperation):
    def __init__(self, *args, **kwargs):
        super(DicomGet, self).__init__(*args, **kwargs)

        self.query_model = PatientRootQueryRetrieveInformationModelGet
        if not self.config.patient_root_query_model:
            self.query_model = StudyRootQueryRetrieveInformationModelGet

        self.folder = None
        self.callback = None

    def _handle_store(self, event):
        """Handle a C-STORE request event."""
        ds = event.dataset
        context = event.context

        # Add DICOM File Meta Information
        meta = Dataset()
        meta.MediaStorageSOPClassUID = ds.SOPClassUID
        meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
        meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION
        meta.TransferSyntaxUID = context.transfer_syntax
        ds.file_meta = meta

        # Set the transfer syntax attributes of the dataset
        ds.is_little_endian = context.transfer_syntax.is_little_endian
        ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

        # Save the dataset using the SOP Instance UID as the filename in an optional folder
        filename = ds.SOPInstanceUID
        if self.folder:
            filename = os.path.join(self.folder, filename)

        # Allow to manipuate the dataset by using a callback before saving to disk
        if self.callback:
            self.callback(ds)

        ds.save_as(filename, write_like_original=False)

        # Return a 'Success' status
        return 0x0000

    def open(self):
        ae = AE(ae_title=self.config.client_ae_title)

        # See https://github.com/pydicom/pynetdicom/issues/459
        # and https://github.com/pydicom/pynetdicom/blob/master/pynetdicom/apps/getscu/getscu.py#L222
        cx = list(QueryRetrievePresentationContexts)
        nr_pc = len(QueryRetrievePresentationContexts)
        cx += StoragePresentationContexts[: 128 - nr_pc]
        ae.requested_contexts = cx
        negotiation_items = []
        for context in StoragePresentationContexts[: 128 - nr_pc]:
            role = build_role(context.abstract_syntax, scp_role=True)
            negotiation_items.append(role)

        handlers = [(evt.EVT_C_STORE, self._handle_store)]

        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
            ext_neg=negotiation_items,
            evt_handlers=handlers,
        )

        if not self.assoc.is_established:
            raise ConnectionError(
                "Could not connect to DICOM server with AE Title %s."
                % self.config.server_ae_title
            )

    @connect_to_server
    def send_c_get(self, query_dict, folder=None, callback=None, msg_id=1):
        """
        Download DICOM instances to a local folder.

        Parameters:
            query_dict (dict): The DICOM query what instances to fetch
            folder (str): A folder name or folder path where to put the instances

        Returns:
            A dict of responses
        """
        self.callback = callback

        self.folder = folder
        if self.folder:
            Path(self.folder).mkdir(parents=True, exist_ok=True)

        ds = make_query_dataset(query_dict)

        # The Synapse PACS server only accepts study root queries (not patient root queries)
        # for C-GET requests
        responses = self.assoc.send_c_get(ds, self.query_model, msg_id)

        results = []
        for status, ds in responses:
            if status:
                results.append(
                    {
                        "status": {
                            "code": status.Status,
                            "category": code_to_category(status.Status),
                        },
                        "data": dictify_dataset(ds),
                    }
                )
            else:
                logging.error(
                    "Invalid connection during C-GET with query: %s", str(query_dict)
                )

        return results


class DicomStore(DicomOperation):
    def open(self):
        ae = AE(ae_title=self.config.client_ae_title)
        ae.requested_contexts = StoragePresentationContexts
        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
        )

        if not self.assoc.is_established:
            raise ConnectionError(
                "Could not connect to DICOM server with AE Title %s."
                % self.config.server_ae_title
            )

    @connect_to_server
    def send_c_store(self, folder, callback=None, msg_id=1):
        results = []
        for root, _, files in os.walk(folder):
            for filename in files:
                filepath = os.path.join(root, filename)
                ds = dcmread(filepath)

                # Allow to manipuate the dataset by using a callback before storing to server
                if callback:
                    callback(ds)

                status = self.assoc.send_c_store(ds, msg_id)

                if status:
                    status_category = code_to_category(status.Status)

                    data_dict = {}
                    if status_category in ["WARNING", "FAILURE", "CANCEL"]:
                        data_dict = {"SOPInstanceUID": ds.SOPInstanceUID}

                    results.append(
                        {
                            "status": {
                                "code": status.Status,
                                "category": status_category,
                            },
                            "data": data_dict,
                        }
                    )
                else:
                    logging.error(
                        "Invalid connection during C-STORE with folder: %s", folder
                    )

        return results


class DicomMove(DicomOperation):
    def __init__(self, *args, **kwargs):
        super(DicomMove, self).__init__(*args, **kwargs)

        self.query_model = PatientRootQueryRetrieveInformationModelMove
        if not self.config.patient_root_query_model:
            self.query_model = StudyRootQueryRetrieveInformationModelMove

    def open(self):
        ae = AE(ae_title=self.config.client_ae_title)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
        )

        if not self.assoc.is_established:
            raise ConnectionError(
                "Could not connect to DICOM server with AE Title %s."
                % self.config.server_ae_title
            )

    @connect_to_server
    def send_c_move(self, query_dict, destination_ae_title, msg_id=1):
        query_ds = make_query_dataset(query_dict)

        responses = self.assoc.send_c_move(
            query_ds, destination_ae_title, self.query_model, msg_id
        )

        results = []
        for status, ds in responses:
            if status:
                results.append(
                    {
                        "status": {
                            "code": status.Status,
                            "category": code_to_category(status.Status),
                        },
                        "data": dictify_dataset(ds),
                    }
                )
            else:
                logging.error(
                    "Invalid connection during C-MOVE with query: %s", str(query_dict)
                )

        return results
