from doctest import Example
import logging
import re
import os

import xnat
from typing import Dict, List, Literal, Union, Any
import time
import datetime
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from pydicom import dcmread
from pydicom.filereader import dcmread
from pynetdicom import debug_logger

from django.conf import settings
from adit.core.models import DicomServer
from adit.core.errors import RetriableTaskError

from adit.core.utils.sanitize import sanitize_dirname
from adit.core.utils.dicom_utils import format_datetime_attributes
from adit.core.utils.dicom_connector import (
    _check_required_id, 
    _dictify_dataset,
    _save_dicom_from_receiver,
    _sanitize_query_dict,
)


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

    def __init__(self, server: DicomServer, config: Config = None, xnat_project_id: str = ""):
        self.server = server
        if config is None:
            self.config = XnatConnector.Config()
        else:
            self.config = config

        if settings.DICOM_DEBUG_LOGGER:
            debug_logger()  # Debug mode of pynetdicom

        self.xnat_project_id = xnat_project_id
        
        # Setting up the connection at connector initialization saves ~1-2s per connector usage.
        self.session = _connect_to_xnat_server(self.server)

    def find_patients(self, query, limit_results=None):

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

        query["QueryRetrieveLevel"] = "SERIES"
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
        
        return list(
            filter(
                lambda x: x["Modality"] == modality or x["Modality"] in modality,
                series_list,
            )
        )
        
    def download_study(  # pylint: disable=too-many-arguments
        self,
        patient_id,
        study_uid,
        folder,
        modality=None,
        modifier_callback=None,
    ):
        series_list = self.find_series(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "Modality": modality,
                "SeriesInstanceUID": "",
                "SeriesDescription": "",
            }
        )
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            # TODO maybe we should move the series folder name creation to the
            # store handler as it is not guaranteed that all PACS servers
            # do return the SeriesDescription with C-FIND
            series_folder_name = sanitize_dirname(series["SeriesDescription"])
            download_path = Path(folder) / series_folder_name

            self.download_series(
                patient_id, study_uid, series_uid, download_path, modifier_callback
            )

        logger.debug("Successfully downloaded study %s.", study_uid)

    def download_series(  # pylint: disable=too-many-arguments
        self, 
        patient_id, 
        study_uid, 
        series_uid, 
        folder, 
        modifier_callback=None
    ):
        """Download all series to a specified folder for given series UIDs and pseudonymize
        the dataset before storing it to disk."""

        query = {
            "QueryRetrieveLevel": "SERIES",
            "PatientID": patient_id,
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
        }

        self._send_xnat_get(query, folder, modifier_callback)
        logger.debug(
            "Successfully downloaded series %s of study %s.", series_uid, study_uid
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
            xnat_project_id=self.xnat_project_id, 
        )

        query_results = []
        for ds in xnat_results:
            query_results.append(_dictify_dataset(ds))
        
        return query_results

    def _send_xnat_get(
        self, 
        query_dict,
        folder, 
        modifier_callback=None,
    ):
        logger.debug("Sending XNAT get requerst with query: %s", query_dict)
        study_uid = _check_required_id(query_dict.get("StudyInstanceUID"))
        series_uid = _check_required_id(query_dict.get("SeriesInstanceUID"))

        series = _get_xnat_scan(
            {"StudyInstanceUID": study_uid, "SeriesInstanceUID": series_uid},
            self.session,
            xnat_project_id=self.xnat_project_id,
        )

        for ds in series:
            if modifier_callback:
                modifier_callback(ds)
            _save_dicom_from_receiver(ds, folder)

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


def _xnat_query(query, session, download_path=None):
    results = []
    for xnat_project_id in session.projects:
    #for xnat_project_id in session.select.projects().get():
        project_results = _xnat_query_projects(
            query, session, xnat_project_id, download_path=download_path,
        )
        results.extend(project_results)
    return results


def _xnat_query_projects(query, session, xnat_project_id, download_path=None):
    results = []
    for experiment_id in session.projects[xnat_project_id].experiments:
        experiment_results = _xnat_query_experiments(
            query, session, xnat_project_id, experiment_id, download_path=download_path,
        )
        results.extend(experiment_results)
    return results


def _xnat_query_experiments(query, session, xnat_project_id, experiment_id, download_path=None):
    results = []
    for scan_id in session.projects[xnat_project_id].experiments[experiment_id].scans:
        scan_results = (
            session.projects[xnat_project_id]
            .experiments[experiment_id]
            .scans[scan_id]
            .read_dicom()
        )
        match = True
        for attribute, value in query.items():
            try:
                if value!="" and attribute=="StudyDate":
                    if not studydate_in_range(value, scan_results[attribute].value):
                        match = False
                        break
                elif value != "" and value != scan_results[attribute].value:
                        match = False
                        break

            except KeyError:
                break

        if match:
            if download_path:
                file_path = download_path / (xnat_project_id+experiment_id+scan_id+".zip")
                session.projects[xnat_project_id].experiments[experiment_id].scans[scan_id].download(file_path)
                results.append(file_path)
            else:
                scan_results.NumberOfSeriesRelatedInstances = session.projects[xnat_project_id].experiments[experiment_id].scans[scan_id].frames
                scan_results.Modality = session.projects[xnat_project_id].experiments[experiment_id].scans[scan_id].modality
                results.append(scan_results)

    return results


def _find_xnat_scan(query, session, xnat_project_id=None, experiment_id=None):
    if not xnat_project_id:
        return _xnat_query(query, session)
    elif not experiment_id:
        return _xnat_query_projects(query, session, xnat_project_id)
    else:
        return _xnat_query_experiments(query, session, xnat_project_id, experiment_id)


def _get_xnat_scan(query, session, xnat_project_id=None, experiment_id=None):
    download_path = Path("adit/xnat_support/tmp") / (query["StudyInstanceUID"]+query["SeriesInstanceUID"])
    download_path.mkdir(parents=True, exist_ok=True)

    if not xnat_project_id:
        temp_paths = _xnat_query(query, session, download_path=download_path)
    elif not experiment_id:
        temp_paths = _xnat_query_projects(query, session, xnat_project_id, download_path=download_path)
    else:
        temp_paths = _xnat_query_experiments(query, session, xnat_project_id, experiment_id, download_path=download_path)

    series = []
    for path in temp_paths:
        zip_file = ZipFile(path)
        for dicom_instance in list(filter(lambda name: "DICOM" in name, zip_file.namelist())):
            with zip_file.open(dicom_instance) as ds_binary:
                series.append(dcmread(ds_binary))
        os.remove(path)
    os.rmdir(download_path)

    return series

def studydate_in_range(value, scan_study_date):
    time = datetime.datetime.strptime(scan_study_date, settings.DICOM_DATE_FORMAT)
    times = value.split("-")
    if len(times)==2:
        start_time = datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT)
        end_time = datetime.datetime.strptime(times[1], settings.DICOM_DATE_FORMAT)
        if time<start_time or time>end_time:
            return False
    elif len(times)==1:
        if value[0]=="-":
            end_time = datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT)
            if time>end_time:
                return False
        elif value[-1]=="-":
            start_time = start_time = datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT)
            if time<start_time:
                return False
        else:
            if time!=datetime.datetime.strptime(times[0], settings.DICOM_DATE_FORMAT):
                return False
    return True