import logging
import traceback

import pydicom
from dicognito.anonymizer import Anonymizer
from dicognito.element_anonymizer import ElementAnonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset

logger = logging.getLogger(__name__)


class DateTimeLoggingHandler(ElementAnonymizer):
    """
    A logging handler that inspects and logs datetime DICOM elements
    before they are shifted by the DateTimeAnonymizer.
    """

    def __call__(self, dataset: Dataset, data_element: pydicom.DataElement) -> bool:
        """
        Log datetime elements (DA and DT) for debugging purposes.

        Returns False so that the actual DateTimeAnonymizer can still process the element.
        """
        if data_element.VR not in ("DA", "DT"):
            return False

        # Get related time element if this is a date element
        time_value = None
        if data_element.VR == "DA":
            time_name = data_element.keyword.replace("Date", "Time")
            if time_name in dataset:
                time_element = dataset.data_element(time_name)
                if time_element and time_element.value:
                    time_value = time_element.value

        logger.debug(
            "DEBUG DateTimeShift: Element %s (tag: %s, VR: %s) = %r%s",
            data_element.keyword,
            data_element.tag,
            data_element.VR,
            data_element.value,
            f", corresponding Time ({time_name}) = {time_value!r}" if time_value else "",
        )

        # Return False to allow the DateTimeAnonymizer to process the element
        return False

    def describe_actions(self):
        """Describe the actions this handler performs."""
        yield "Log all DA and DT elements before datetime shifting"


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

        # Add datetime logging handler for debugging datetime shifts
        anonymizer.add_element_handler(DateTimeLoggingHandler())

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
        manufacturer = getattr(ds, "Manufacturer", "Unknown")
        manufacturer_model = getattr(ds, "ManufacturerModelName", "Unknown")
        software_versions = getattr(ds, "SoftwareVersions", "Unknown")
        station_name = getattr(ds, "StationName", "Unknown")

        logger.debug(
            "DEBUG pseudonymize: Manufacturer details for image %s - "
            "Manufacturer: %s, Model: %s, Software: %s, Station: %s",
            sop_instance_uid,
            manufacturer,
            manufacturer_model,
            software_versions,
            station_name,
        )

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
