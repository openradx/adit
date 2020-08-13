import logging
import time
from dataclasses import dataclass
from pathlib import Path
import os
from functools import partial
from pydicom.dataset import Dataset
from pydicom import dcmread, valuerep, uid
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


def _make_query_dataset(query_dict):
    """Turn a dict into a pydicom dataset for query."""

    ds = Dataset()
    for i in query_dict:
        setattr(ds, i, query_dict[i])
    return ds


def _sanitise_unicode(s):
    return s.replace(u"\u0000", "").strip()


def _convert_value(v):
    t = type(v)
    if t in (list, int, float):
        cv = v
    elif t == str:
        cv = _sanitise_unicode(v)
    elif t == bytes:
        s = v.decode("ascii", "replace")
        cv = _sanitise_unicode(s)
    elif t == valuerep.DSfloat:
        cv = float(v)
    elif t == valuerep.IS:
        cv = int(v)
    elif t == valuerep.PersonName:
        cv = str(v)
    elif t == uid.UID:
        cv = str(v)
    else:
        cv = repr(v)
    return cv


def _dictify_dataset(ds):
    """Turn a pydicom Dataset into a dict with keys derived from the Element tags.

    Adapted from https://github.com/pydicom/pydicom/issues/319
    """
    output = dict()

    for elem in ds:
        # We only use non private tags as keywords may not be unique when
        # there are also private tags present.
        # See also https://github.com/pydicom/pydicom/issues/319
        if elem.tag.is_private:
            continue

        if elem.tag == (0x7FE0, 0x0010):  # discard PixelData
            continue

        if elem.VR != "SQ":
            output[elem.keyword] = _convert_value(elem.value)
        else:
            output[elem.keyword] = [_dictify_dataset(item) for item in elem]

    return output


def _extract_results(responses, operation, query_dict):
    results = []
    for status, ds in responses:
        if status:
            data = {}
            if ds:
                data.update(_dictify_dataset(ds))

            results.append(
                {
                    "status": {
                        "code": status.Status,
                        "category": code_to_category(status.Status),
                    },
                    "data": data,
                }
            )
        else:
            logging.error(
                "Association rejected, aborted or never connected during %s with query: %s.",
                operation,
                str(query_dict),
            )

    return results


def _handle_store(folder, callback, event):
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
    if folder:
        filename = os.path.join(folder, filename)

    # Allow to manipuate the dataset by using a callback before saving to disk
    if callback:
        callback(ds)

    ds.save_as(filename, write_like_original=False)

    # Return a 'Success' status
    return 0x0000


class DicomConnector:
    @dataclass
    class Config:  # pylint: disable=too-many-instance-attributes
        client_ae_title: str
        server_ae_title: str
        server_ip: str
        server_port: int
        patient_root_query_model_find: bool = True
        patient_root_query_model_get: bool = True
        patient_root_query_model_move: bool = True
        debug: bool = False
        connection_retries: int = 3
        retry_timeout: int = 30  # in seconds

    def __init__(self, config: Config):
        self.config = config

        if config.debug:
            debug_logger()

        if config.patient_root_query_model_find:
            self.find_query_model = PatientRootQueryRetrieveInformationModelFind
        else:
            self.find_query_model = StudyRootQueryRetrieveInformationModelFind

        if config.patient_root_query_model_get:
            self.get_query_model = PatientRootQueryRetrieveInformationModelGet
        else:
            self.get_query_model = StudyRootQueryRetrieveInformationModelGet

        if config.patient_root_query_model_move:
            self.move_query_model = PatientRootQueryRetrieveInformationModelMove
        else:
            self.move_query_model = StudyRootQueryRetrieveInformationModelMove

        self.assoc = None

    def _associate(self):
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

        self.assoc = ae.associate(
            self.config.server_ip,
            self.config.server_port,
            ae_title=self.config.server_ae_title,
            ext_neg=negotiation_items,
        )

        if not self.assoc.is_established:
            raise ConnectionError(
                "Could not connect to DICOM server with AE Title %s."
                % self.config.server_ae_title
            )

    def open_connection(self):
        if self.assoc is None or not self.assoc.is_alive():
            for i in range(self.config.connection_retries):
                try:
                    self._associate()
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

    def close_connection(self):
        if self.assoc:
            self.assoc.release()
            self.assoc = None

    def find(self, query_dict, msg_id=1):
        query_ds = _make_query_dataset(query_dict)

        responses = self.assoc.send_c_find(query_ds, self.find_query_model, msg_id)
        return _extract_results(responses, "C-Find", query_dict)

    def get(self, query_dict, folder=None, callback=None, msg_id=1):
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)

        ds = _make_query_dataset(query_dict)

        handle_store = partial(_handle_store, folder, callback)
        self.assoc.bind(evt.EVT_C_STORE, handle_store)

        # The Synapse PACS server only accepts study root queries (not patient root queries)
        # for C-GET requests
        responses = self.assoc.send_c_get(ds, self.get_query_model, msg_id)
        results = _extract_results(responses, "C-GET", query_dict)

        self.assoc.unbind(evt.EVT_C_STORE, handle_store)

        return results

    def move(self, query_dict, destination_ae_title, msg_id=1):
        query_ds = _make_query_dataset(query_dict)

        responses = self.assoc.send_c_move(
            query_ds, destination_ae_title, self.move_query_model, msg_id
        )
        return _extract_results(responses, "C-MOVE", query_dict)

    def store(self, folder, callback=None, msg_id=1):
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
                    results.append(
                        {
                            "status": {
                                "code": status.Status,
                                "category": code_to_category(status.Status),
                            },
                            "data": {"SOPInstanceUID": ds.SOPInstanceUID},
                        }
                    )
                else:
                    logging.error(
                        "Invalid connection during C-STORE with folder: %s", folder
                    )

        return results
