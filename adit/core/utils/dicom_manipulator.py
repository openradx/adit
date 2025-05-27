from typing import Optional

from pydicom.dataset import Dataset

from adit.core.utils.pseudonymizer import Pseudonymizer


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
        if pseudonym:
            self.pseudonymizer.pseudonymize(ds, pseudonym)

        if trial_protocol_id:
            ds.TrialProtocolID = trial_protocol_id

        if trial_protocol_name:
            ds.TrialProtocolName = trial_protocol_name

        if pseudonym and trial_protocol_id:
            session_id = f"{ds.StudyDate}-{ds.StudyTime}"
            ds.PatientComments = (
                f"Project:{trial_protocol_id} Subject:{pseudonym} Session:{pseudonym}_{session_id}"
            )
