from functools import partial
from main.utils.dicom_transferrer import DicomTransferrer

class BatchTransferrer(DicomTransferrer):
    def batch_transfer(self, data, progress_callback):
        pass

    def _modify_dataset(self, pseudonym, ds):
        """Pseudonymize an incoming dataset with the given pseudonym and add the trial
        name to the DICOM header if specified."""

        if self.config.pseudonymize:
            self._anonymizer.anonymize_dataset(ds, patient_name=pseudonym)

        if self.config.clinical_trial_protocol_id:
            ds.ClinicalTrialProtocolID = self.config.clinical_trial_protocol_id
        
        if self.config.clinical_trial_protocol_name:
            ds.ClinicalTrialProtocolName = self.config.clinical_trial_protocol_name