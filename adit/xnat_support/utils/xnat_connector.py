from doctest import Example
import logging
import re

import xnat
import pyxnat
from typing import Dict, List, Literal, Union, Any
import time
import datetime
from dataclasses import dataclass
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import errno
from functools import wraps
import pika
from pydicom.dataset import Dataset
from pydicom import dcmread, valuerep, uid
from pydicom.datadict import dictionary_VM
from pydicom.errors import InvalidDicomError
from pydicom.filereader import dcmread
from pynetdicom import debug_logger

from pynetdicom.status import (
    code_to_category,
    STATUS_PENDING,
    STATUS_SUCCESS,
)
from django.conf import settings
from adit.core.models import DicomServer
from adit.core.errors import RetriableTaskError

from adit.core.utils.sanitize import sanitize_dirname
from adit.core.utils.dicom_utils import format_datetime_attributes


logger = logging.getLogger(__name__)


def _connect_to_xnat_server(server):
    return xnat.connect(
        server.xnat_root_url,
        user=server.xnat_username,
        password=server.xnat_password,
    )
    
class XnatConnector:
    @dataclass
    class Config:
        auto_connect: bool = True
        connection_retries: int = 2
        retry_timeout: int = 30  # in seconds
        acse_timeout: int = None
        dimse_timeout: int = None
        network_timeout: int = None

    def __init__(self, server: DicomServer, config: Config = None, project_id: str = "", experiment_id: str = ""):
        self.server = server
        if config is None:
            self.config = XnatConnector.Config()
        else:
            self.config = config

        if settings.DICOM_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

        self.project_id = project_id
        self.experiment_id = experiment_id
        
        # Setting up the connection at connector initialization saves ~1-2s per connector usage.
        self.session = _connect_to_xnat_server(self.server)

    def find_patients(self, query, limit_results=None):

        if self.server.xnat_rest_source:
            query["QueryRetrieveLevel"] = "STUDY"
            patients = self._send_xnat_find(
                query,
                limit_results=limit_results,
            )

        # Make patients unique, since querying on study level will return all 
        # studies for one patient, resulting in duplicate patients
        if query["QueryRetrieveLevel"] == "STUDY":
            seen = set()
            unique_patients = [
                patient
                for patient in patients
                if patient["PatientID"] not in seen
                and not seen.add(patient["PatientID"])
            ]
            patients = unique_patients

        return patients

    def find_studies(self, query, limit_results=None):
        query["QueryRetrieveLevel"] = "STUDY"

        if not "NumberOfStudyRelatedInstances" in query:
            query["NumberOfStudyRelatedInstances"] = ""

        if self.server.xnat_rest_source:
            query["QueryRetrieveLevel"] = "STUDY"
            studies = self._send_xnat_find(
                query,
                limit_results=limit_results,
            )

        # make studies unique
        seen = set()
        unique_studies = [
            study
            for study in studies
            if study["StudyInstanceUID"] not in seen
            and not seen.add(study["StudyInstanceUID"])
        ]

        # find study level attributes, which are lost on Xnat
        for unique_study in unique_studies:
            frames = 0
            modalities = []
            for study in studies:
                if unique_study["StudyInstanceUID"]==study["StudyInstanceUID"]:
                    frames += study.get("NumberOfSeriesRelatedInstances", 0)
                    if study.get("Modality") and not study.get("Modality") in modalities:
                        modalities.append(study["Modality"])
            unique_study["ModalitiesInStudy"] = modalities
            unique_study["NumberOfStudyRelatedInstances"] = frames

        studies = unique_studies

        query_modalities = query.get("ModalitiesInStudy")
        if not query_modalities:
            return studies

        return self._filter_studies_by_modalities(studies, query_modalities)

    def find_series(self, query, limit_results=None):

        query["QueryRetrieveLevel"] = "SERIES"

        # We handle query filter for Modality programmatically because we allow
        # to filter for multiple modalities.
        modality = query.get("Modality")
        if modality:
            query["Modality"] = ""

        series_description = query.get("SeriesDescription")
        if series_description:
            series_description = series_description.lower()
            query["SeriesDescription"] = ""

        if self.server.xnat_rest_source:
            query["QueryRetrieveLevel"] = "SERIES"
            logger.debug("at find_series")
            logger.debug(query)
            series_list = self._send_xnat_find(
                query,
                limit_results=limit_results,
            )

        if series_description:
            series_list = list(
                filter(
                    lambda x: re.search(
                        series_description, x["SeriesDescription"].lower()
                    ),
                    series_list,
                )
            )

        if not modality:
            return series_list
        
        logger.debug(series_list)
        return list(
            filter(
                lambda x: x["Modality"] == modality or x["Modality"] in modality,
                series_list,
            )
        )
        

    def fetch_study_modalities(self, patient_id, study_uid):
        """Fetch all modalities of a study and return them in a list."""

        try:
            series_list = self.find_series(
                {"PatientID": patient_id, "StudyInstanceUID": study_uid, "Modality": ""}
            )
        except ValueError as err:
            logger.exception("Failed to fetch modalities of study %s.", study_uid)
            raise RetriableTaskError("Failed to fetch modalities of study.") from err

        modalities = set(map(lambda x: x["Modality"], series_list))
        return sorted(list(modalities))

    def _send_xnat_find(
        self,
        query_dict,
        limit_results=None,
        msg_id=1,
    ):
        logger.debug("Sending XNAT find requerst with query: %s", query_dict)
        level = query_dict.get("QueryRetreiveLevel")

        query = _sanitize_query_dict(query_dict)

        xnat_results = _find_xnat_scan(
            query, 
            self.session, 
            project_id=self.project_id, 
            experiment_id=self.experiment_id,
        )

        query_results = []
        for ds in xnat_results:
            query_results.append(_dictify_dataset(ds))
        
        return query_results

    def _fetch_results(self, responses, operation, query_dict, limit_results=None):
        results = []
        for (status, identifier) in responses:
            if limit_results is not None and len(results) >= limit_results:
                self.abort_connection()
                break

            if status:
                data = {}
                if identifier:
                    data.update(_dictify_dataset(identifier))

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
                logger.error(
                    "Connection timed out, was aborted or received invalid "
                    "response during %s with query: {%s}",
                    operation,
                    query_dict,
                )
                raise RetriableTaskError(
                    "Connection timed out, was aborted or received invalid "
                    f"during {operation}."
                )
        return results

    # TODO remove pylint disable, see https://github.com/PyCQA/pylint/issues/3882
    # pylint: disable=unsubscriptable-object
    def _filter_studies_by_modalities(
        self, studies: List[Dict[str, Any]], query_modalities: Union[str, List[str]]
    ) -> List[Dict[str, Any]]:
        filtered_studies = []
        for study in studies:
            study_modalities = study.get("ModalitiesInStudy")
            number_images = int(study.get("NumberOfStudyRelatedInstances") or 1)

            if study_modalities and isinstance(study_modalities, list):
                filtered_studies.append(study)

            elif study_modalities and isinstance(study_modalities, str):
                # ModalitiesInStudy returns multiple modalities in a list, but only one
                # modality as a string (at least with the Synapse PACS). So we convert the
                # later one to a list.
                study["ModalitiesInStudy"] = [study_modalities]
                filtered_studies.append(study)

            elif not study_modalities and number_images == 0:
                filtered_studies.append(study)

            elif not study_modalities and number_images > 0:
                # Modalities In Study is not supported by all PACS servers. If it is
                # supported then it should be not empty. Otherwise we fetch the modalities
                # of all the series of this study manually.
                study["ModalitiesInStudy"] = self.fetch_study_modalities(
                    study["PatientID"], study["StudyInstanceUID"]
                )

                # When modalities were fetched manually then the studies must also be
                # filtered manually. Cave, when limit_results is used this may lead to less
                # studies then there really exist.
                if (
                    isinstance(query_modalities, str)
                    and query_modalities in study["ModalitiesInStudy"]
                ):
                    filtered_studies.append(study)

                if isinstance(query_modalities, list) and (
                    set(query_modalities) & set(study["ModalitiesInStudy"])
                ):
                    filtered_studies.append(study)

            else:
                raise AssertionError(f"Invalid study modalities: {study_modalities}")

        return filtered_studies

    def _consume_dicoms(  # pylint: disable=too-many-arguments
        self,
        study_uid,
        series_uid,
        image_uids,
        folder,
        modifier_callback,
        move_stopped_event: threading.Event,
    ):
        remaining_image_uids = image_uids[:]

        for message in self._consume_with_timeout(
            study_uid, series_uid, move_stopped_event
        ):
            received_image_uid, data = message

            if received_image_uid in remaining_image_uids:
                ds = dcmread(data)

                if received_image_uid != ds.SOPInstanceUID:
                    raise AssertionError(
                        f"Received wrong image with UID {ds.SOPInstanceUID}. "
                        f"Expected UID {received_image_uid}."
                    )

                if modifier_callback:
                    modifier_callback(ds)

                _save_dicom_from_receiver(ds, folder)

                remaining_image_uids.remove(received_image_uid)

                # Stop if all images of this series were received
                if not remaining_image_uids:
                    break

        if remaining_image_uids:
            if remaining_image_uids == image_uids:
                logger.error("No images of series %s received.", series_uid)
                raise RetriableTaskError("Failed to download all images with C-MOVE.")

            logger.error(
                "These images of series %s were not received: %s",
                series_uid,
                ", ".join(remaining_image_uids),
            )
            raise RetriableTaskError("Failed to download some images with C-MOVE.")

    def _consume_with_timeout(self, study_uid, series_uid, move_stopped_event):
        last_consume_at = time.time()
        for message in self._consume_from_receiver(study_uid, series_uid):
            method, properties, body = message

            # If we are waiting without a message for more then a specified timeout
            # then we stop waiting anymore and also abort an established association
            time_since_last_consume = time.time() - last_consume_at
            timeout = settings.C_MOVE_DOWNLOAD_TIMEOUT
            if time_since_last_consume > timeout:
                logger.error(
                    "C-MOVE download timed out after %d seconds without receiving images.",
                    round(time_since_last_consume),
                )
                if not move_stopped_event.is_set():
                    logger.warning("Aborting not finished C-MOVE operation.")
                    self.abort_connection()

                break

            # We just reached an inactivity timeout
            if not method:
                continue

            # Reset our timer if a real new message arrives
            last_consume_at = time.time()

            received_image_uid = properties.message_id
            data = BytesIO(body)

            yield received_image_uid, data

    def _consume_from_receiver(self, study_uid, series_uid):
        connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
        channel = connection.channel()
        channel.exchange_declare(exchange="received_dicoms", exchange_type="direct")
        result = channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue
        routing_key = f"{self.server.ae_title}\\{study_uid}\\{series_uid}"
        channel.queue_bind(
            exchange="received_dicoms",
            queue=queue_name,
            routing_key=routing_key,
        )

        try:
            yield from channel.consume(queue_name, auto_ack=True, inactivity_timeout=1)
        finally:
            channel.close()
            connection.close()


def _check_required_id(value):
    if value and not "*" in value and not "?" in value:
        return value
    return None


def _make_query_dataset(query_dict: Dict[str, Any]):
    """Turn a dict into a pydicom dataset for query."""
    ds = Dataset()
    for keyword in query_dict:
        setattr(ds, keyword, query_dict[keyword])
    return ds


def _dictify_dataset(ds: Dataset):
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

        if elem.VR == "SQ":
            output[elem.keyword] = [_dictify_dataset(item) for item in elem]
        else:
            v = elem.value

            # We don't use the optional automatic `pydicom.config.datetime_conversion` as
            # it is globally set and we can't use date ranges then anymore for the
            # queries. See https://github.com/pydicom/pydicom/issues/1293
            if elem.VR == "DA":
                v = valuerep.DA(v)
            elif elem.VR == "DT":
                v = valuerep.DT(v)
            elif elem.VR == "TM":
                v = valuerep.TM(v)

            cv = _convert_value(v)

            # An element with a (possible) multiplicity of > 1 should always be returned
            # as list, even with only one element in it (e.g. ModalitiesInStudy)
            vm = dictionary_VM(elem.tag)
            if vm == "1-n" and not isinstance(cv, list):
                cv = [cv]

            output[elem.keyword] = cv

    return output


def _dicom_json_to_adit_json(results: list) -> list:
    adit_results = []
    for instance in results:
        ds = Dataset.from_json(instance)
        adit_results.append(_dictify_dataset(ds))
    return adit_results


def _convert_value(v: Any):
    """Converts a pydicom value to native Python value."""
    t = type(v)
    if t in (int, float, type(None)):
        cv = v
    elif t == str:
        cv = _sanitize_unicode(v)
    elif t == bytes:
        cv = _sanitize_unicode(v.decode("ascii", "replace"))
    elif t in (uid.UID, valuerep.PersonName):
        cv = str(v)
    elif t == valuerep.IS:
        cv = int(v)
    elif t == valuerep.DSfloat:
        cv = float(v)
    elif t == valuerep.DA:
        cv = datetime.date.fromisoformat(v.isoformat())
    elif t == valuerep.DT:
        cv = datetime.datetime.fromisoformat(v.isoformat())
    elif t == valuerep.TM:
        cv = datetime.time.fromisoformat(v.isoformat())
    elif t in (valuerep.MultiValue, list):
        cv = [_convert_value(i) for i in v]
    else:
        cv = repr(v)
    return cv


def _sanitize_unicode(s: str):
    return s.replace("\u0000", "").strip()


def _extract_pending_data(results: List[Dict[str, Any]]):
    """Extract the data from a DicomOperation result."""
    status_category = results[-1]["status"]["category"]
    status_code = results[-1]["status"]["code"]
    if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
        raise ValueError(f"{status_category} ({status_code}) occurred during C-FIND.")

    filtered = filter(lambda x: x["status"]["category"] == STATUS_PENDING, results)
    data = map(lambda x: x["data"], filtered)
    return list(data)


def _evaluate_get_move_results(results, query):
    status_category = results[-1]["status"]["category"]
    status_code = results[-1]["status"]["code"]
    if status_category not in [STATUS_PENDING, STATUS_SUCCESS]:
        data = results[-1]["data"]
        failed_image_uids = data or data.get("FailedSOPInstanceList")
        error_msg = (
            f"{status_category} ({status_code}) occurred while transferring "
            f"the series with UID {query['SeriesInstanceUID']}."
        )
        if failed_image_uids:
            error_msg += f" Failed images: {', '.join(failed_image_uids)}"
        logger.error(error_msg)
        raise RetriableTaskError(
            f"Failed to transfer images with status {status_category}."
        )


def _save_dicom_from_receiver(ds, folder):
    folder_path = Path(folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    file_path = folder_path / ds.SOPInstanceUID

    # In this case we don't need to save with `write_like_original=False` as it
    # saved already saved it this way to the buffer in the receiver
    try:
        ds.save_as(str(file_path), write_like_original=False)
    except OSError as err:
        if err.errno == errno.ENOSPC:  # No space left on device
            logger.exception("Out of disk space while saving %s.", file_path)
            raise RetriableTaskError(
                "Out of disk space on destination.", long_delay=True
            ) from err

        raise err


def _filter_by_query(query: dict, unfiltered_list: list) -> list:
    filter_attributes = ["PatientID", "StudyInstanceUID", "SeriesInstanceUID"]
    filterd_list = unfiltered_list
    for attribute, value in query.items():
        if attribute in filter_attributes and not value == "":
            filterd_list = _filter_by_attribute(attribute, value, filterd_list)
    return filterd_list


def _filter_by_attribute(attribute: str, value: str, unfiltered_list: list) -> list:
    filtered_list = []
    for instance in unfiltered_list:
        if attribute in list(instance.keys()):  # can filter by that attribute
            if instance[attribute] == value:
                filtered_list.append(instance)
        else:  # cannot filter by that attribute
            filtered_list.append(instance)
    return filtered_list


def _sanitize_query_dict(query_dict: dict) -> dict:
    query = query_dict.copy()
    filter_values = ["*", None]
    for attribute, value in query_dict.items():
        if value in filter_values:
            query[attribute] = ""

    del query["QueryRetrieveLevel"]

    if query.get("PatientBirthDate"):
        try:
            query["PatientBirthDate"] = query["PatientBirthDate"].strftime("%Y%m%d")
        except TypeError:
            pass

    return query


def _xnat_query(query, session):
    results = []
    for project_id in session.projects:
    #for project_id in session.select.projects().get():
        project_results = _xnat_query_projects(query, session, project_id)
        results.extend(project_results)
    return results


def _xnat_query_projects(query, session, project_id):
    results = []
    for experiment_id in session.projects[project_id].experiments:
    #for experiment_id in session.select.projects(project_id).subjects().experiments().get():
        experiment_results = _xnat_query_experiments(
            query, session, project_id, experiment_id
        )
        results.extend(experiment_results)
    return results


def _xnat_query_experiments(query, session, project_id, experiment_id):
    results = []
    for scan_id in session.projects[project_id].experiments[experiment_id].scans:
    #for scan_id in session.select.projects(project_id).subjects().experiments(experiment_id).get():
        logger.debug(project_id)
        scan_results = (
            session.projects[project_id]
            .experiments[experiment_id]
            .scans[scan_id]
            .read_dicom()
        )
        match = True
        for attribute, value in query.items():
            try:
                if value!="" and attribute=="StudyDate":
                    time = datetime.datetime.strptime(scan_results[attribute].value, settings.DICOM_DATE_FORMAT)
                    times = value.split("-")
                    if len(times)==2:
                        start_time = datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT)
                        end_time = datetime.datetime.strptime(times[1], settings.DICOM_DATE_FORMAT)
                        if time<start_time or time>end_time:
                            match = False
                            break
                    elif len(times)==1:
                        if value[0]=="-":
                            end_time = datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT)
                            if time>end_time:
                                match = False
                                break
                        elif value[-1]=="-":
                            start_time = start_time = datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT)
                            if time<start_time:
                                match = False
                                break
                        else:
                            if time!=datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT):
                                match = False
                                break

                elif value != "" and value != scan_results[attribute].value:
                        match = False
                        break

            except KeyError:
                break
        if match:
            scan_results.NumberOfSeriesRelatedInstances = session.projects[project_id].experiments[experiment_id].scans[scan_id].frames
            scan_results.Modality = session.projects[project_id].experiments[experiment_id].scans[scan_id].modality
            results.append(scan_results)
    return results


def _find_xnat_scan(query, session, project_id=None, experiment_id=None):
    if not project_id:
        return _xnat_query(query, session)
    elif not experiment_id:
        return _xnat_query_projects(query, session, project_id)
    else:
        return _xnat_query_experiments(query, session, project_id, experiment_id)
