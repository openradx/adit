from pydicom.dataset import Dataset

from adit.core.utils.pseudonymizer import Pseudonymizer


class DicomManipulator:
    def __init__(self, pseudonymizer: Pseudonymizer | None = None):
        self.pseudonymizer = pseudonymizer or Pseudonymizer()

    def manipulate(
        self,
        ds: Dataset,
        pseudonym: str | None = None,
        trial_protocol_id: str | None = None,
        trial_protocol_name: str | None = None,
    ) -> None:
        """
        Manipulates the DICOM dataset by pseudonymizing and setting trial protocol details.

        Args:
            ds (Dataset): The DICOM dataset to manipulate.
            pseudonym (Optional[str]): The pseudonym to set for the PatientID.
            trial_protocol_id (Optional[str]): The trial protocol ID to set.
            trial_protocol_name (Optional[str]): The trial protocol name to set.
        """
        if pseudonym:
            self.pseudonymizer.pseudonymize(ds, pseudonym)

        if trial_protocol_id:
            ds.ClinicalTrialProtocolID = trial_protocol_id

        if trial_protocol_name:
            ds.ClinicalTrialProtocolName = trial_protocol_name

        if pseudonym and trial_protocol_id:
            session_id = f"{ds.StudyDate}-{ds.StudyTime}"
            ds.PatientComments = (
                f"Project:{trial_protocol_id} Subject:{pseudonym} Session:{pseudonym}_{session_id}"
            )
