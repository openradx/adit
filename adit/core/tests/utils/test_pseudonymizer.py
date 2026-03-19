import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import UID

from adit.core.utils.pseudonymizer import Pseudonymizer


@pytest.fixture
def pseudonymizer():
    return Pseudonymizer()


def create_base_dataset() -> Dataset:
    """Create a minimal valid DICOM dataset for testing."""
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


class TestPseudonymizer:
    def test_pseudonymize_sets_patient_id_and_name(self, pseudonymizer: Pseudonymizer):
        ds = create_base_dataset()
        pseudonym = "TEST_PSEUDONYM"

        pseudonymizer.pseudonymize(ds, pseudonym)

        assert ds.PatientID == pseudonym
        assert ds.PatientName == pseudonym

    def test_pseudonymize_with_empty_pseudonym_raises_error(self, pseudonymizer: Pseudonymizer):
        ds = create_base_dataset()

        with pytest.raises(ValueError, match="valid pseudonym must be provided"):
            pseudonymizer.pseudonymize(ds, "")

    def test_pseudonymize_with_none_pseudonym_raises_error(self, pseudonymizer: Pseudonymizer):
        ds = create_base_dataset()

        with pytest.raises(ValueError, match="valid pseudonym must be provided"):
            pseudonymizer.pseudonymize(ds, None)  # type: ignore

    def test_pseudonymize_with_frame_reference_datetime(self, pseudonymizer: Pseudonymizer):
        """Test that FrameReferenceDateTime elements don't cause anonymization to fail.

        This test verifies the fix for batch transfer tasks failing when DICOM files
        contain FrameReferenceDateTime elements with non-standard datetime formats.
        The FrameReferenceDateTime element should be skipped during anonymization.
        """
        ds = create_base_dataset()
        # Add FrameReferenceDateTime with a value that could cause parsing issues
        ds.FrameReferenceDateTime = "202301011200005"  # Non-standard format with extra digit
        pseudonym = "TEST_PSEUDONYM"

        # This should not raise an exception
        pseudonymizer.pseudonymize(ds, pseudonym)

        assert ds.PatientID == pseudonym
        assert ds.PatientName == pseudonym
        # FrameReferenceDateTime should be preserved (not anonymized)
        assert ds.FrameReferenceDateTime == "202301011200005"

    def test_pseudonymize_preserves_study_date_and_time(self, pseudonymizer: Pseudonymizer):
        """Test that StudyDate and StudyTime are preserved during anonymization."""
        ds = create_base_dataset()
        original_study_date = ds.StudyDate
        original_study_time = ds.StudyTime
        pseudonym = "TEST_PSEUDONYM"

        pseudonymizer.pseudonymize(ds, pseudonym)

        assert ds.StudyDate == original_study_date
        assert ds.StudyTime == original_study_time

    def test_pseudonymize_preserves_acquisition_datetime(self, pseudonymizer: Pseudonymizer):
        """Test that AcquisitionDateTime is preserved during anonymization."""
        ds = create_base_dataset()
        ds.AcquisitionDateTime = "20230101120000"
        pseudonym = "TEST_PSEUDONYM"

        pseudonymizer.pseudonymize(ds, pseudonym)

        assert ds.AcquisitionDateTime == "20230101120000"


class TestComputePseudonym:
    def test_requires_seed(self):
        ps = Pseudonymizer()
        with pytest.raises(ValueError, match="requires a seeded Pseudonymizer"):
            ps.compute_pseudonym("PAT1")

    def test_deterministic_same_seed(self):
        """Same seed + same patient ID always produces the same pseudonym."""
        ps1 = Pseudonymizer(seed="fixed-seed")
        ps2 = Pseudonymizer(seed="fixed-seed")
        assert ps1.compute_pseudonym("PAT1") == ps2.compute_pseudonym("PAT1")

    def test_different_seeds_produce_different_pseudonyms(self):
        ps1 = Pseudonymizer(seed="seed-a")
        ps2 = Pseudonymizer(seed="seed-b")
        assert ps1.compute_pseudonym("PAT1") != ps2.compute_pseudonym("PAT1")

    def test_different_patients_produce_different_pseudonyms(self):
        ps = Pseudonymizer(seed="fixed-seed")
        assert ps.compute_pseudonym("PAT1") != ps.compute_pseudonym("PAT2")

    def test_matches_dicognito_anonymize(self):
        """compute_pseudonym must match what dicognito produces for PatientID."""
        seed = "test-consistency-seed"
        ps = Pseudonymizer(seed=seed)
        pseudonym = ps.compute_pseudonym("PATIENT_42")

        # Run the full anonymizer on a real dataset and check the PatientID
        # before our pseudonymize() overwrites it.
        from dicognito.anonymizer import Anonymizer

        anon = Anonymizer(seed=seed)
        ds = create_base_dataset()
        ds.PatientID = "PATIENT_42"
        anon.anonymize(ds)
        assert ds.PatientID == pseudonym

    def test_pseudonym_is_alphanumeric(self):
        ps = Pseudonymizer(seed="alpha-seed")
        result = ps.compute_pseudonym("SOME_PATIENT")
        assert result.isalnum()
        assert result == result.upper()
