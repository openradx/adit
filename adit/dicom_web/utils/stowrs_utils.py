import logging
from datetime import datetime
from typing import List

import pydicom
from adrf.views import sync_to_async
from django.urls import reverse
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from adit.core.models import DicomServer
from adit.core.utils.dicom_connector import DicomConnector

logger = logging.getLogger(__name__)


async def stow_store(dest_server: DicomServer, datasets: List[Dataset]):
    connector = DicomConnector(dest_server)

    logger.info("Connected to server %s", dest_server.ae_title)

    result_dict = {}

    for ds in datasets:
        assert isinstance(ds, Dataset)

        if ds.StudyInstanceUID not in result_dict:
            result_dict[ds.StudyInstanceUID] = pydicom.Dataset()
            result_dict[ds.StudyInstanceUID].RetrieveURL = reverse(
                "wado_rs-studies_with_study_uid",
                args=[dest_server.ae_title, ds.StudyInstanceUID],
            )
            result_dict[ds.StudyInstanceUID].FailedSOPSequence = pydicom.Sequence([])
            result_dict[ds.StudyInstanceUID].ReferencedSOPSequence = pydicom.Sequence([])

        result_ds = pydicom.Dataset()
        result_ds.SOPClassUID = ds.SOPClassUID
        result_ds.SOPInstanceUID = ds.SOPInstanceUID
        result_ds.OriginalAttributesSequence = pydicom.Sequence([])

        original_attributes = await remove_unknow_vr_attributes(ds)

        try:
            await sync_to_async(connector.upload_instances)([ds])
            result_ds.RetrieveURL = reverse(
                "wado_rs-series_with_study_uid_and_series_uid",
                args=[dest_server.ae_title, ds.StudyInstanceUID, ds.SeriesInstanceUID],
            )
            result_ds.OriginalAttributesSequence = original_attributes
            result_dict[ds.StudyInstanceUID].ReferencedSOPSequence.append(result_ds)

        except Exception as e:
            logger.error("Failed to upload dataset %s", ds.SOPInstanceUID)
            logger.error(e)
            result_ds.FailureReason = "0110"
            result_dict[ds.StudyInstanceUID].FailedSOPSequence.append(result_ds)

    return list(result_dict.values())


async def remove_unknow_vr_attributes(ds: Dataset) -> Sequence:
    original_attributes = pydicom.Sequence([])
    for elem in ds:
        if elem.VR == "UN":
            modification_ds = pydicom.Dataset()
            modification_ds.AttributeModificationDateTime = datetime.now().strftime("%Y%m%d%H%M%S")
            modification_ds.ModifyingSystem = "ADIT"
            modification_ds.ReasonForTheAttributeModification = "VR_UNKNOWN"

            try:
                elem.value = str(elem.value)
            except ValueError:
                elem.value = "not serializable"
            elem.VR = "ST"
            elem_ds = pydicom.Dataset()
            elem_ds[elem.tag] = elem
            modification_ds.ModifiedAttributesSequence = pydicom.Sequence([elem_ds])

            original_attributes.append(modification_ds)
            del elem

    return original_attributes
