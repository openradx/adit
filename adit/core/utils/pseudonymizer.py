import hashlib
import string

from dicognito.anonymizer import Anonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset

_PSEUDONYM_ALPHABET = string.ascii_uppercase + string.digits  # A-Z0-9


def compute_pseudonym(seed: str, identifier: str, length: int) -> str:
    """Derive a pseudonym from a seed and identifier using SHA-256.

    Uses the same divmod extraction approach as dicognito's IDAnonymizer
    but with SHA-256 instead of MD5 for stability and security.
    """
    digest = hashlib.sha256((seed + identifier).encode("utf8")).digest()
    big_int = int.from_bytes(digest, "big")
    chars = []
    for _ in range(length):
        big_int, idx = divmod(big_int, len(_PSEUDONYM_ALPHABET))
        chars.append(_PSEUDONYM_ALPHABET[idx])
    return "".join(chars)


class Pseudonymizer:
    """
    A utility class for pseudonymizing (or anonymizing) DICOM data.
    """

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
