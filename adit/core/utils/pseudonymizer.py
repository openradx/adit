import logging
import traceback

from dicognito.anonymizer import Anonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset

logger = logging.getLogger(__name__)


class Pseudonymizer:
    """
    A utility class for pseudonymizing (or anonymizing) DICOM data.
    """

    def __init__(self) -> None:
        """
        Initialize the Pseudonymizer.

        Sets up the anonymizer instance and configures it to skip specific elements.
        """
        self.anonymizer = self._setup_anonymizer()

    def _setup_anonymizer(self) -> Anonymizer:
        """
        Set up the anonymizer instance and configure it to skip specific elements.

        :return: An instance of the Anonymizer class.
        """
        anonymizer = Anonymizer()
        for element in settings.SKIP_ELEMENTS_ANONYMIZATION:
            anonymizer.add_element_handler(ValueKeeper(element))
        return anonymizer

    def pseudonymize(self, ds: Dataset, pseudonym: str) -> None:
        """
        Pseudonymize the given DICOM dataset using the anonymizer and the provided pseudonym.

        :param ds: The DICOM dataset to be pseudonymized.
        :param pseudonym: The pseudonym to be applied to the dataset.
        :raises ValueError: If the pseudonym is None or empty.
        """
        if not pseudonym:
            raise ValueError("A valid pseudonym must be provided for pseudonymization.")

        sop_instance_uid = getattr(ds, "SOPInstanceUID", "Unknown")
        sop_class_uid = getattr(ds, "SOPClassUID", "Unknown")
        modality = getattr(ds, "Modality", "Unknown")

        logger.debug(
            "DEBUG pseudonymize: Starting anonymization for image %s "
            "(SOPClassUID: %s, Modality: %s, Pseudonym: %s)",
            sop_instance_uid,
            sop_class_uid,
            modality,
            pseudonym,
        )

        try:
            self.anonymizer.anonymize(ds)
            logger.debug(
                "DEBUG pseudonymize: Anonymization completed for image %s", sop_instance_uid
            )
        except Exception as err:
            logger.error(
                "DEBUG pseudonymize: Anonymization FAILED for image %s "
                "(SOPClassUID: %s, Modality: %s): %s\n%s",
                sop_instance_uid,
                sop_class_uid,
                modality,
                str(err),
                traceback.format_exc(),
            )
            raise

        ds.PatientID = pseudonym
        ds.PatientName = pseudonym
        logger.debug(
            "DEBUG pseudonymize: Set PatientID and PatientName to %s for image %s",
            pseudonym,
            sop_instance_uid,
        )
