from dicognito.anonymizer import Anonymizer
from dicognito.randomizer import Randomizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset


class Pseudonymizer:
    """
    A utility class for pseudonymizing (or anonymizing) DICOM data.
    """

    _ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    _ID_LENGTH = 12

    def __init__(
        self,
        anonymizer: Anonymizer | None = None,
        seed: str | None = None,
    ) -> None:
        """
        Initialize the Pseudonymizer.

        Sets up the anonymizer instance and configures it to skip specific elements.
        If an existing Anonymizer is provided, it will be used instead of creating a new one.
        When a seed is provided, the anonymizer produces deterministic results —
        the same input always maps to the same output.
        """
        self._seed = seed
        self.anonymizer = anonymizer or self._setup_anonymizer(seed=seed)

    def _setup_anonymizer(self, seed: str | None = None) -> Anonymizer:
        """
        Set up the anonymizer instance and configure it to skip specific elements.

        :return: An instance of the Anonymizer class.
        """
        anonymizer = Anonymizer(seed=seed)
        for element in settings.SKIP_ELEMENTS_ANONYMIZATION:
            anonymizer.add_element_handler(ValueKeeper(element))
        return anonymizer

    def compute_pseudonym(self, patient_id: str) -> str:
        """Pre-compute the pseudonym for a patient ID without a full DICOM dataset.

        Uses the same algorithm as dicognito's IDAnonymizer so the result
        matches what anonymize() would produce for PatientID.
        Requires that this Pseudonymizer was created with a seed.
        """
        if self._seed is None:
            raise ValueError("compute_pseudonym requires a seeded Pseudonymizer")
        randomizer = Randomizer(self._seed)
        ranges = [len(self._ALPHABET)] * self._ID_LENGTH
        indices = randomizer.get_ints_from_ranges(patient_id, *ranges)
        return "".join(self._ALPHABET[i] for i in indices)

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
