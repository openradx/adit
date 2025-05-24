from dicognito.anonymizer import Anonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset


class Pseudonymizer:
    """
    A utility class for pseudonymizing (or anonymizing) DICOM data.
    """

    def __init__(self, pseudonym: str | None = None) -> None:
        """
        Initialize the Pseudonymizer with an optional pseudonym.

        :param pseudonym: The pseudonym to be used for the DICOM data.
        """
        self.anonymizer = self._setup_anonymizer()
        self.pseudonym = pseudonym

    def _setup_anonymizer(self) -> Anonymizer:
        """
        Set up the anonymizer instance and configure it to skip specific elements.

        :return: An instance of the Anonymizer class.
        """
        anonymizer = Anonymizer()
        for element in settings.SKIP_ELEMENTS_ANONYMIZATION:
            anonymizer.add_element_handler(ValueKeeper(element))
        return anonymizer

    def pseudonymize(
        self,
        ds: Dataset,
    ) -> None:
        """
        Pseudonymize the given DICOM dataset using the anonymizer and optional pseudonym.

        :param ds: The DICOM dataset to be pseudonymized.
        """
        if self.pseudonym:
            # Replace PatientID and PatientName with the provided pseudonym.
            self.anonymizer.anonymize(ds)  # Apply anonymization to the dataset.
            ds.PatientID = self.pseudonym
            ds.PatientName = self.pseudonym
