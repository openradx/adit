import logging

import pydicom
from dicognito.anonymizer import Anonymizer
from dicognito.element_anonymizer import ElementAnonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset

logger = logging.getLogger(__name__)


class DateTimeLoggingHandler(ElementAnonymizer):
    """
    A logging handler that inspects and logs the FrameReferenceDateTime element
    before it is shifted by the DateTimeAnonymizer.
    """

    def __call__(self, _dataset: Dataset, data_element: pydicom.DataElement) -> bool:
        """
        Log FrameReferenceDateTime element for debugging purposes.

        Returns False so that the actual DateTimeAnonymizer can still process the element.
        """
        if data_element.keyword != "FrameReferenceDateTime":
            return False

        logger.debug(
            "DEBUG DateTimeShift: FrameReferenceDateTime (tag: %s, VR: %s) = %r",
            data_element.tag,
            data_element.VR,
            data_element.value,
        )

        # Return False to allow the DateTimeAnonymizer to process the element
        return False

    def describe_actions(self):
        """Describe the actions this handler performs."""
        yield "Log FrameReferenceDateTime element before datetime shifting"


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

        self.anonymizer.anonymize(ds)
        ds.PatientID = pseudonym
        ds.PatientName = pseudonym
