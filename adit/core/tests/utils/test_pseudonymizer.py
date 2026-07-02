import pytest
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.uid import UID

from adit.core.utils.pseudonymizer import Pseudonymizer, compute_pseudonym


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

    @pytest.mark.filterwarnings("ignore:Invalid value for VR DT:UserWarning")
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

    def test_pseudonymize_removes_common_phi(self, pseudonymizer: Pseudonymizer):
        """PHI sweep: identifying tags must not survive anonymization with their original values.

        The other tests only check that PatientID/PatientName are set and that the kept date
        fields survive. This guards the inverse: a future change to the de-identification path
        must not silently stop scrubbing a PHI field. We assert the *original* value is gone
        (using .get so a removed element passes too), not the specific replacement.
        """
        ds = create_base_dataset()
        ds.PatientBirthDate = "19800101"
        ds.PatientAddress = "123 Secret Street"
        ds.PatientTelephoneNumbers = "555-0100"
        ds.OtherPatientIDs = "OTHER-ID-999"
        ds.AccessionNumber = "ACC-123456"
        ds.ReferringPhysicianName = "Referring^Doctor"
        ds.PerformingPhysicianName = "Performing^Doctor"
        ds.InstitutionName = "Secret Hospital"
        ds.InstitutionAddress = "456 Hospital Road"

        pseudonymizer.pseudonymize(ds, "PSEUDONYM123")

        # Patient identity is replaced with the pseudonym ...
        assert ds.PatientID == "PSEUDONYM123"
        assert ds.PatientName == "PSEUDONYM123"
        # ... and none of the original identifying values survive in their fields.
        assert str(ds.get("PatientBirthDate", "")) != "19800101"
        assert str(ds.get("PatientAddress", "")) != "123 Secret Street"
        assert str(ds.get("PatientTelephoneNumbers", "")) != "555-0100"
        assert str(ds.get("OtherPatientIDs", "")) != "OTHER-ID-999"
        assert str(ds.get("AccessionNumber", "")) != "ACC-123456"
        assert str(ds.get("ReferringPhysicianName", "")) != "Referring^Doctor"
        assert str(ds.get("PerformingPhysicianName", "")) != "Performing^Doctor"
        assert str(ds.get("InstitutionName", "")) != "Secret Hospital"
        assert str(ds.get("InstitutionAddress", "")) != "456 Hospital Road"

    def test_pseudonymize_regenerates_instance_uids(self, pseudonymizer: Pseudonymizer):
        """Study/Series/SOP UIDs are regenerated so the output can't be linked by original UID."""
        ds = create_base_dataset()
        original_study_uid = ds.StudyInstanceUID
        original_series_uid = ds.SeriesInstanceUID
        original_sop_uid = ds.SOPInstanceUID

        pseudonymizer.pseudonymize(ds, "PSEUDONYM123")

        assert ds.StudyInstanceUID != original_study_uid
        assert ds.SeriesInstanceUID != original_series_uid
        assert ds.SOPInstanceUID != original_sop_uid


class TestComputePseudonym:
    def test_deterministic_same_seed(self):
        """Same seed + same identifier always produces the same pseudonym."""
        result1 = compute_pseudonym("fixed-seed", "PAT1", 14)
        result2 = compute_pseudonym("fixed-seed", "PAT1", 14)
        assert result1 == result2

    def test_different_seeds_produce_different_pseudonyms(self):
        result1 = compute_pseudonym("seed-a", "PAT1", 14)
        result2 = compute_pseudonym("seed-b", "PAT1", 14)
        assert result1 != result2

    def test_different_identifiers_produce_different_pseudonyms(self):
        result1 = compute_pseudonym("fixed-seed", "PAT1", 14)
        result2 = compute_pseudonym("fixed-seed", "PAT2", 14)
        assert result1 != result2

    def test_length(self):
        assert len(compute_pseudonym("seed", "PAT1", 14)) == 14
        assert len(compute_pseudonym("seed", "PAT1", 8)) == 8

    def test_pseudonym_is_uppercase_alphanumeric(self):
        result = compute_pseudonym("alpha-seed", "SOME_PATIENT", 14)
        assert result.isalnum()
        assert result == result.upper()

    def test_stable_output(self):
        """Pseudonyms must not change across code updates (breaks cross-transfer linking)."""
        assert compute_pseudonym("my-salt", "PAT1", 12) == "81T9LZGKTAM3"
        assert compute_pseudonym("my-salt", "PAT1", 14) == "81T9LZGKTAM3UV"
