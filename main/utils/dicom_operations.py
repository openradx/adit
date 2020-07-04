import logging
import time
from pathlib import Path
import os
from dataclasses import dataclass
from pydicom.dataset import Dataset
from pydicom import dcmread
from pynetdicom import (
    AE, evt, build_role, debug_logger,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)
from pynetdicom.sop_class import ( # pylint: disable-msg=no-name-in-module
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelMove
)
from pynetdicom.status import code_to_category

def connect_to_server(func):
    def wrapper(self, *args, **kwargs):
        if self.assoc is None or not self.assoc.isAlive():
            for _ in range(self.config.connection_retries):
                connected = False
                try:
                    self.open()
                    connected = True
                except Exception as ex:
                    logging.error("Could not connect to server: %s" % str(ex))
                    logging.warn("Retrying to connect.")
                    time.sleep(self.config.retry_timeout)

                if connected:
                    break

        result = None
        exception_occurred = False
        try:
            result = func(self, *args, **kwargs)
        except Exception as ex:
            logging.error("An error occurred during DICOM operation %s: %s"
                % (func.__name__, str(ex)))
            exception_occurred = True
        finally:
            if exception_occurred or self.config.auto_close_connection:
                self.close()

        return result
    return wrapper


@dataclass
class DicomOperationConfig:
    client_ae_title: str
    server_ae_title: str
    server_ip: str
    server_port: int
    patient_root_query_model: bool = True
    auto_close_connection: bool = True
    debug: bool = False
    connection_retries: int = 3
    retry_timeout: int = 300 # in seconds


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
        results = [{
            'status': {'code': status.Status, 'category': code_to_category(status.Status)},
            'data': {}
        }]
        return results

    def dictify_dataset(self, ds):
        """Turn a pydicom Dataset into a dict with keys derived from the Element tags.

        Args:
            ds (pydicom.dataset.Dataset): The Dataset to dictify

        Returns:
            A Python dict
        """
        output = dict()
        if ds:
            for elem in ds:
                # We only use non private tags as keywords may not be unique when
                # there are also private tags present.
                # See also https://github.com/pydicom/pydicom/issues/319
                if elem.tag.is_private:
                    continue

                if elem.VR != 'SQ':
                    output[elem.keyword] = elem.value
                else:
                    output[elem.keyword] = [self.dictify_dataset(item) for item in elem]
        return output

    def make_query_dataset(self, query_dict):
        """Turn a dict into a pydicom Dataset.

        Args:
            query_dict (dict): The dict to turn into a pydicom Dataset

        Return:
            A pydicom Dataset
        """
        ds = Dataset()
        for i in query_dict:
            setattr(ds, i, query_dict[i])
        return ds


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
            ae_title=self.config.server_ae_title)

        if not self.assoc.is_established:
            raise Exception('Association rejected, aborted or never connected.')

    @connect_to_server
    def send_c_find(self, query_dict):
        query_ds = self.make_query_dataset(query_dict)
        
        responses = self.assoc.send_c_find(
            query_ds,
            self.query_model
        )

        results = []
        for status, ds in responses:
            if status:
                # TODO check if this is more appropriate
                # status_dict = self.dictify(status)
                # status_dict['status_category'] = code_to_category(status.Status)
                # query_response['status'].append(status_dict)

                results.append({
                    'status': {'code': status.Status, 'category': code_to_category(status.Status)},
                    'data': self.dictify_dataset(ds)
                })
            else:
                logging.error("Invalid connection during C-Find with query: %s" % (str(query_dict)))

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
        cx += StoragePresentationContexts[:128 - nr_pc]
        ae.requested_contexts = cx
        negotiation_items = []
        for context in StoragePresentationContexts[:128 - nr_pc]:
            role = build_role(context.abstract_syntax, scp_role=True)
            negotiation_items.append(role)

        handlers = [(evt.EVT_C_STORE, self._handle_store)]

        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
            ext_neg=negotiation_items,
            evt_handlers=handlers)

        if not self.assoc.is_established:
            raise Exception('Association rejected, aborted or never connected.')

    @connect_to_server
    def send_c_get(self, query_dict, folder=None, callback=None):
        """
        Download DICOM instances to a local folder.

        Parameters:
            query_dict (dict): The DICOM query what instances to fetch
            folder (str): A folder name or folder path where to put the instances

        Returns:
            A dict of responses
        """
        self.callback = callback
        if self.callback is not None and not callable(self.callback):
            raise ValueError("A callback must be a callable function")

        self.folder = folder
        if self.folder:
            Path(self.folder).mkdir(parents=True, exist_ok=True)

        ds = self.make_query_dataset(query_dict)

        # The Synapse PACS server only accepts study root queries (not patient root queries)
        # for C-GET requests
        responses = self.assoc.send_c_get(ds, self.query_model)

        results = []
        for status, ds in responses:
            if status:
                results.append({
                    'status': {'code': status.Status, 'category': code_to_category(status.Status)},
                    'data': self.dictify_dataset(ds)
                })
            else:
                logging.error("Invalid connection during C-GET with query: %s" % (str(query_dict)))

        return results


class DicomStore(DicomOperation):
    def __init__(self, *args, **kwargs):
        super(DicomStore, self).__init__(*args, **kwargs)

    def open(self):
        ae = AE(ae_title=self.config.client_ae_title)
        ae.requested_contexts = StoragePresentationContexts
        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title)

        if not self.assoc.is_established:
            raise Exception('Association rejected, aborted or never connected.')

    @connect_to_server
    def send_c_store(self, folder, callback=None):
        results = []
        for root, _, files in os.walk(folder):
            for filename in files:
                filepath = os.path.join(root, filename)
                ds = dcmread(filepath)

                # Allow to manipuate the dataset by using a callback before storing to server
                if callback:
                    callback(ds)

                status = self.assoc.send_c_store(ds)

                if status:
                    status_category = code_to_category(status.Status)

                    data_dict = {}
                    if (status_category in ['WARNING', 'FAILURE', 'CANCEL']):
                        data_dict = {"SOPInstanceUID": ds.SOPInstanceUID}
                    
                    results.append({
                        'status': {'code': status.Status, 'category': status_category},
                        'data': data_dict
                    })
                else:
                    logging.error("Invalid connection during C-STORE with folder: %s" % (folder))

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
            ae_title=self.config.server_ae_title)

        if not self.assoc.is_established:
            raise Exception('Association rejected, aborted or never connected.')

    @connect_to_server
    def send_c_move(self, query_dict, destination_ae_title):
        query_ds = self.make_query_dataset(query_dict)

        responses = self.assoc.send_c_move(query_ds, destination_ae_title, self.query_model)

        results = []
        for status, ds in responses:
            if status:
                results.append({
                    'status': {'code': status.Status, 'category': code_to_category(status.Status)},
                    'data': self.dictify_dataset(ds)
                })
            else:
                logging.error("Invalid connection during C-MOVE with query: %s" % (str(query_dict)))

        return results
