import logging
from datetime import datetime

from adrf.views import sync_to_async
from django.urls import reverse
from pydicom import Dataset, Sequence

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator

from ..errors import BadGatewayApiError, ServiceUnavailableApiError

logger = logging.getLogger(__name__)


async def stow_store(dest_server: DicomServer, ds: Dataset) -> tuple[Dataset, bool]:
    operator = DicomOperator(dest_server)

    logger.info("Connected to server %s", dest_server.ae_title)

    assert isinstance(ds, Dataset)

    result_ds = Dataset()
    result_ds.SOPClassUID = ds.SOPClassUID
    result_ds.SOPInstanceUID = ds.SOPInstanceUID
    result_ds.OriginalAttributesSequence = Sequence([])

    original_attributes = await remove_unknow_vr_attributes(ds)

    try:
        await sync_to_async(operator.upload_images, thread_sensitive=False)([ds])
        result_ds.RetrieveURL = reverse(
            "wado_rs-series_with_study_uid_and_series_uid",
            args=[dest_server.ae_title, ds.StudyInstanceUID, ds.SeriesInstanceUID],
        )
        result_ds.OriginalAttributesSequence = original_attributes
        return result_ds, False
    except RetriableDicomError as err:
        logger.exception(err)
        raise ServiceUnavailableApiError(str(err))
    except DicomError as err:
        logger.exception(err)
        raise BadGatewayApiError(str(err))
    except Exception as err:
        logger.exception(err)
        logger.error("Failed to upload dataset %s", ds.SOPInstanceUID)

        # https://dicom.nema.org/medical/dicom/current/output/html/part18.html#sect_I.2.2
        result_ds.FailureReason = "0110"  # Processing failure

    return result_ds, True


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
