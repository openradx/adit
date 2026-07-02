import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import UID

from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.pseudonymizer import Pseudonymizer


def create_base_dataset() -> Dataset:
    """Create a minimal valid DICOM dataset for testing.

    Mirrors the dataset-building pattern used in test_pseudonymizer.py so the
    manipulator is exercised against a dataset dicognito can actually anonymize.
    """
    ds = Dataset()
    ds.PatientID = "ORIGINAL_ID"
    ds.PatientName = "Original^Name"
    ds.StudyInstanceUID = "1.2.3.4.5"
    ds.SeriesInstanceUID = "1.2.3.4.5.6"
    ds.SOPInstanceUID = "1.2.3.4.5.6.7"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    ds.Modality = "CT"
    ds.StudyDate = "20230101"
    ds.StudyTime = "120000"

    # Add file_meta as required by dicognito
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = UID(ds.SOPClassUID)
    file_meta.MediaStorageSOPInstanceUID = UID(ds.SOPInstanceUID)
    file_meta.TransferSyntaxUID = UID("1.2.840.10008.1.2")  # Implicit VR Little Endian
    ds.file_meta = file_meta

    return ds


class FakePseudonymizer:
    """A stand-in Pseudonymizer that records calls instead of anonymizing.

    Lets us assert the manipulator's orchestration (when it does/doesn't delegate,
    and with what pseudonym) without depending on dicognito's behavior.
    """

    def __init__(self):
        self.calls: list[tuple[Dataset, str]] = []

    def pseudonymize(self, ds: Dataset, pseudonym: str) -> None:
        self.calls.append((ds, pseudonym))
        # Emulate the real contract: PatientID/PatientName become the pseudonym.
        ds.PatientID = pseudonym
        ds.PatientName = pseudonym


@pytest.fixture
def fake_pseudonymizer() -> FakePseudonymizer:
    return FakePseudonymizer()


class TestDicomManipulatorConstruction:
    def test_defaults_to_real_pseudonymizer(self):
        manipulator = DicomManipulator()
        assert isinstance(manipulator.pseudonymizer, Pseudonymizer)

    def test_accepts_injected_pseudonymizer(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        assert manipulator.pseudonymizer is fake_pseudonymizer


class TestManipulatePseudonymization:
    def test_pseudonym_is_delegated_to_pseudonymizer(
        self, fake_pseudonymizer: FakePseudonymizer
    ):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="PSEUDO123")

        assert len(fake_pseudonymizer.calls) == 1
        called_ds, called_pseudonym = fake_pseudonymizer.calls[0]
        assert called_ds is ds
        assert called_pseudonym == "PSEUDO123"

    def test_no_pseudonym_skips_pseudonymizer(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym=None)

        assert fake_pseudonymizer.calls == []
        # Untouched identity when no pseudonym is given.
        assert ds.PatientID == "ORIGINAL_ID"
        assert ds.PatientName == "Original^Name"

    def test_empty_pseudonym_skips_pseudonymizer(self, fake_pseudonymizer: FakePseudonymizer):
        """An empty string is falsy, so the manipulator must not delegate (and must
        not trip the real pseudonymizer's empty-pseudonym ValueError)."""
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="")

        assert fake_pseudonymizer.calls == []

    def test_manipulate_returns_none(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()
        assert manipulator.manipulate(ds, pseudonym="PSEUDO123") is None


class TestManipulateWithRealPseudonymizer:
    """End-to-end through the real Pseudonymizer/dicognito stack (no DB needed)."""

    def test_real_pseudonymization_sets_identity(self):
        manipulator = DicomManipulator()
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="REALPSEUDO")

        assert ds.PatientID == "REALPSEUDO"
        assert ds.PatientName == "REALPSEUDO"
        # Original identifier must not survive.
        assert ds.PatientID != "ORIGINAL_ID"

    def test_real_pseudonymization_preserves_study_date_time(self):
        """StudyDate/StudyTime are in SKIP_ELEMENTS_ANONYMIZATION, so they must
        survive — the PatientComments session_id below relies on this."""
        manipulator = DicomManipulator()
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="REALPSEUDO")

        assert ds.StudyDate == "20230101"
        assert ds.StudyTime == "120000"


class TestManipulateTrialProtocol:
    def test_sets_trial_protocol_id(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, trial_protocol_id="TRIAL-1")

        assert ds.ClinicalTrialProtocolID == "TRIAL-1"

    def test_sets_trial_protocol_name(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, trial_protocol_name="My Trial")

        assert ds.ClinicalTrialProtocolName == "My Trial"

    def test_no_trial_protocol_leaves_attrs_unset(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="PSEUDO123")

        assert "ClinicalTrialProtocolID" not in ds
        assert "ClinicalTrialProtocolName" not in ds


class TestManipulatePatientComments:
    """The PatientComments line is only written when BOTH a pseudonym and a
    trial_protocol_id are supplied. This is the module's only multi-input branch."""

    def test_patient_comments_set_when_pseudonym_and_protocol_id(
        self, fake_pseudonymizer: FakePseudonymizer
    ):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="PSEUDO123", trial_protocol_id="TRIAL-1")

        expected = "Project:TRIAL-1 Subject:PSEUDO123 Session:PSEUDO123_20230101-120000"
        assert ds.PatientComments == expected

    def test_patient_comments_not_set_with_only_pseudonym(
        self, fake_pseudonymizer: FakePseudonymizer
    ):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="PSEUDO123")

        assert "PatientComments" not in ds

    def test_patient_comments_not_set_with_only_protocol_id(
        self, fake_pseudonymizer: FakePseudonymizer
    ):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds, trial_protocol_id="TRIAL-1")

        assert "PatientComments" not in ds
        assert ds.ClinicalTrialProtocolID == "TRIAL-1"

    def test_patient_comments_uses_original_study_date_time_with_real_pseudonymizer(self):
        """Full stack: the session_id embedded in PatientComments must reflect the
        preserved StudyDate/StudyTime, not anonymized values."""
        manipulator = DicomManipulator()
        ds = create_base_dataset()

        manipulator.manipulate(ds, pseudonym="REALPSEUDO", trial_protocol_id="TRIAL-9")

        assert ds.PatientComments == (
            "Project:TRIAL-9 Subject:REALPSEUDO Session:REALPSEUDO_20230101-120000"
        )


class TestManipulateNoArgs:
    def test_no_args_is_a_noop_for_identity(self, fake_pseudonymizer: FakePseudonymizer):
        manipulator = DicomManipulator(pseudonymizer=fake_pseudonymizer)  # type: ignore[arg-type]
        ds = create_base_dataset()

        manipulator.manipulate(ds)

        assert fake_pseudonymizer.calls == []
        assert ds.PatientID == "ORIGINAL_ID"
        assert ds.PatientName == "Original^Name"
        assert "ClinicalTrialProtocolID" not in ds
        assert "ClinicalTrialProtocolName" not in ds
        assert "PatientComments" not in ds
