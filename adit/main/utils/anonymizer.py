import os
from dataclasses import dataclass
from pathlib import Path
import pydicom


def _person_names_callback(_, data_element):
    if data_element.VR == "PN":
        data_element.value = "Anonymized"


def _curves_callback(ds, data_element):
    if data_element.tag.group & 0xFF00 == 0x5000:
        del ds[data_element.tag]


class Anonymizer:
    @dataclass
    class Config:
        anonymize_patient_id: bool = False
        anonymize_patient_name: bool = True
        normalize_birth_date: bool = True
        anonymize_all_person_names: bool = True
        anomymize_curves: bool = True
        remove_private_tags: bool = True
        remove_other_patient_ids: bool = True

    def __init__(self, config=Config()):
        self.config = config
        self.generated_pseudonyms = []

    def anonymize_dataset(self, ds, pseudonymized_id=None, pseudonymized_name=None):

        if self.config.anonymize_patient_id:
            ds.PatientID = "Anonymized"

        if self.config.anonymize_patient_name:
            ds.PatientName = "Anonymized"

        if self.config.normalize_birth_date:
            birth_date = ds.PatientBirthDate
            ds.PatientBirthDate = birth_date[0:4] + "0101"

        if self.config.anonymize_all_person_names:
            ds.walk(_person_names_callback)

        if self.config.anomymize_curves:
            ds.walk(_curves_callback)

        if self.config.remove_private_tags:
            ds.remove_private_tags()

        if self.config.remove_other_patient_ids:
            if hasattr(ds, "OtherPatientIDs"):
                del ds.OtherPatientIDs
            if hasattr(ds, "OtherPatientIDsSequence"):
                del ds.OtherPatientIDsSequence

        if pseudonymized_id is not None:
            ds.PatientID = pseudonymized_id

        if pseudonymized_name is not None:
            ds.PatientName = pseudonymized_name

        return (ds.PatientID, ds.PatientName)

    def anonymize_folder(self, folder, *args, **kwargs):
        if not Path(folder).is_dir():
            raise ValueError(f"Invalid folder: {folder}")

        callback = kwargs.pop("callback", None)
        if callback is not None and not callable(callback):
            raise ValueError("callback must be callable function")

        for root, _, files in os.walk(folder):
            for filename in files:
                file_path = Path(root) / filename
                ds = pydicom.dcmread(file_path)
                self.anonymize_dataset(ds, *args, **kwargs)

                # Allow to manipulate the dataset before saving it to disk
                if callback:
                    callback(ds)

                ds.save_as(file_path)

        return True
