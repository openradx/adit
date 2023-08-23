import logging
from datetime import datetime

from adrf.views import sync_to_async
from django.urls import reverse
from pydicom import Dataset, Sequence

from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator

logger = logging.getLogger(__name__)


async def stow_store(dest_server: DicomServer, datasets: list[Dataset]) -> list[Dataset]:
    operator = DicomOperator(dest_server)

    logger.info("Connected to server %s", dest_server.ae_title)

    result_dict: dict[str, Dataset] = {}

    for ds in datasets:
        assert isinstance(ds, Dataset)

        if ds.StudyInstanceUID not in result_dict:
            result_dict[ds.StudyInstanceUID] = Dataset()
            result_dict[ds.StudyInstanceUID].RetrieveURL = reverse(
                "wado_rs-studies_with_study_uid",
                args=[dest_server.ae_title, ds.StudyInstanceUID],
            )
            result_dict[ds.StudyInstanceUID].FailedSOPSequence = Sequence([])
            result_dict[ds.StudyInstanceUID].ReferencedSOPSequence = Sequence([])

        result_ds = Dataset()
        result_ds.SOPClassUID = ds.SOPClassUID
        result_ds.SOPInstanceUID = ds.SOPInstanceUID
        result_ds.OriginalAttributesSequence = Sequence([])

        original_attributes = await remove_unknow_vr_attributes(ds)

        try:
            # TODO: really upload one at at time?!
            await sync_to_async(operator.upload_instances)([ds])
            result_ds.RetrieveURL = reverse(
                "wado_rs-series_with_study_uid_and_series_uid",
                args=[dest_server.ae_title, ds.StudyInstanceUID, ds.SeriesInstanceUID],
            )
            result_ds.OriginalAttributesSequence = original_attributes
            result_dict[ds.StudyInstanceUID].ReferencedSOPSequence.append(result_ds)

        except Exception as e:
            logger.error("Failed to upload dataset %s", ds.SOPInstanceUID)
            logger.error(e)

            # https://dicom.nema.org/medical/dicom/current/output/html/part18.html#sect_I.2.2
            result_ds.FailureReason = "0110"  # Processing failure
            result_dict[ds.StudyInstanceUID].FailedSOPSequence.append(result_ds)

    return list(result_dict.values())


async def remove_unknow_vr_attributes(ds: Dataset) -> Sequence:
    original_attributes = Sequence([])
    for elem in ds:
        if elem.VR == "UN":
            modification_ds = Dataset()
            modification_ds.AttributeModificationDateTime = datetime.now().strftime("%Y%m%d%H%M%S")
            modification_ds.ModifyingSystem = "ADIT"
            modification_ds.ReasonForTheAttributeModification = "VR_UNKNOWN"

            try:
                elem.value = str(elem.value)
            except ValueError:
                elem.value = "not serializable"
            elem.VR = "ST"
            elem_ds = Dataset()
            elem_ds[elem.tag] = elem
            modification_ds.ModifiedAttributesSequence = Sequence([elem_ds])

            original_attributes.append(modification_ds)
            del elem

    return original_attributes
