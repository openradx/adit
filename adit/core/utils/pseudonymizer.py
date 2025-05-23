from dicognito.anonymizer import Anonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset


class Pseudonymizer:
    """
    A utility class for pseudonymizing DICOM data using an anonymizer.
    """

    def __init__(self, pseudonym: str | None = None) -> None:
        """
        Initialize the Pseudonymizer with an optional anonymizer instance.

        :param pseudonym: The pseudonym to be used for the DICOM data.
        """
        anonymizer = Anonymizer()
        for element in settings.SKIP_ELEMENTS_ANONYMIZATION:
            anonymizer.add_element_handler(ValueKeeper(element))

        self.anonymizer = anonymizer
        self.pseudonym = pseudonym

    def pseudonymize(
        self,
        ds: Dataset,
    ) -> None:
        """
        Pseudonymize the given data using the provided anonymizer and pseudonym.

        :param ds: The DICOM dataset to be pseudonymized.
        """
        if self.pseudonym is None:
            raise ValueError("Pseudonym is not set.")
        self.anonymizer.anonymize(ds)
        ds.PatientID = self.pseudonym
        ds.PatientName = self.pseudonym
