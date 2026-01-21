import logging
import traceback
from typing import Optional

from pydicom.dataset import Dataset

from adit.core.utils.pseudonymizer import Pseudonymizer

logger = logging.getLogger(__name__)


class DicomManipulator:
    def __init__(self):
        self.pseudonymizer = Pseudonymizer()

    def manipulate(
        self,
        ds: Dataset,
        pseudonym: Optional[str] = None,
        trial_protocol_id: Optional[str] = None,
        trial_protocol_name: Optional[str] = None,
    ) -> None:
        """
        Manipulates the DICOM dataset by pseudonymizing and setting trial protocol details.

        Args:
            ds (Dataset): The DICOM dataset to manipulate.
            pseudonym (Optional[str]): The pseudonym to set for the PatientID.
            trial_protocol_id (Optional[str]): The trial protocol ID to set.
            trial_protocol_name (Optional[str]): The trial protocol name to set.
        """
        sop_instance_uid = getattr(ds, "SOPInstanceUID", "Unknown")
        sop_class_uid = getattr(ds, "SOPClassUID", "Unknown")
        modality = getattr(ds, "Modality", "Unknown")

        logger.debug(
            "DEBUG manipulate: Starting manipulation for image %s "
            "(SOPClassUID: %s, Modality: %s, Pseudonym: %s)",
            sop_instance_uid,
            sop_class_uid,
            modality,
            pseudonym,
        )

        if pseudonym:
            try:
                logger.debug(
                    "DEBUG manipulate: Calling pseudonymizer for image %s", sop_instance_uid
                )
                self.pseudonymizer.pseudonymize(ds, pseudonym)
                logger.debug(
                    "DEBUG manipulate: Pseudonymization completed for image %s", sop_instance_uid
                )
            except Exception as err:
                logger.error(
                    "DEBUG manipulate: Pseudonymization FAILED for image %s "
                    "(SOPClassUID: %s, Modality: %s): %s\n%s",
                    sop_instance_uid,
                    sop_class_uid,
                    modality,
                    str(err),
                    traceback.format_exc(),
                )
                raise

        if trial_protocol_id:
            ds.ClinicalTrialProtocolID = trial_protocol_id
            logger.debug(
                "DEBUG manipulate: Set ClinicalTrialProtocolID to %s for image %s",
                trial_protocol_id,
                sop_instance_uid,
            )

        if trial_protocol_name:
            ds.ClinicalTrialProtocolName = trial_protocol_name
            logger.debug(
                "DEBUG manipulate: Set ClinicalTrialProtocolName to %s for image %s",
                trial_protocol_name,
                sop_instance_uid,
            )

        if pseudonym and trial_protocol_id:
            try:
                session_id = f"{ds.StudyDate}-{ds.StudyTime}"
                ds.PatientComments = (
                    f"Project:{trial_protocol_id} Subject:{pseudonym} "
                    f"Session:{pseudonym}_{session_id}"
                )
                logger.debug(
                    "DEBUG manipulate: Set PatientComments for image %s", sop_instance_uid
                )
            except Exception as err:
                logger.error(
                    "DEBUG manipulate: Failed to set PatientComments for image %s: %s\n%s",
                    sop_instance_uid,
                    str(err),
                    traceback.format_exc(),
                )
                raise

        logger.debug("DEBUG manipulate: Manipulation completed for image %s", sop_instance_uid)
