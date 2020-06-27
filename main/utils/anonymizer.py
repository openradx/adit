import os
import string
import random
import pydicom

class Anonymizer:
    def __init__(
            self,
            anonymize_patient_id=False,
            anonymize_patient_name=True,
            normalize_birth_date=True,
            anonymize_all_person_names=True,
            anomymize_curves=True,
            remove_private_tags=True,
            remove_other_patient_ids=True):

        self.anonymize_patient_id = anonymize_patient_id
        self.anonymize_patient_name = anonymize_patient_name
        self.normalize_birth_date = normalize_birth_date
        self.anonymize_all_person_names = anonymize_all_person_names
        self.anomymize_curves = anomymize_curves
        self.remove_private_tags = remove_private_tags
        self.remove_other_patient_ids = remove_other_patient_ids

        self.generated_pseudonyms = []

    def _person_names_callback(self, ds, data_element):
        if data_element.VR == "PN":
            data_element.value = "Anonymized"

    def _curves_callback(self, ds, data_element):
        if data_element.tag.group & 0xFF00 == 0x5000:
            del ds[data_element.tag]

    def anonymize_dataset(
            self,
            ds,
            patient_id=None,
            patient_name=None):

        if self.anonymize_patient_id:
            ds.PatientID = "Anonymized"

        if self.anonymize_patient_name:
            ds.PatientName = "Anonymized"

        if self.normalize_birth_date:
            birth_date = ds.PatientBirthDate
            ds.PatientBirthDate = birth_date[0:4] + "0101"

        if self.anonymize_all_person_names:
            ds.walk(self._person_names_callback)

        if self.anomymize_curves:
            ds.walk(self._curves_callback)

        if self.remove_private_tags:
            ds.remove_private_tags()

        if self.remove_other_patient_ids:
            if hasattr(ds, 'OtherPatientIDs'):
                del ds.OtherPatientIDs
            if hasattr(ds, 'OtherPatientIDsSequence'):
                del ds.OtherPatientIDsSequence

        if patient_id is not None:
            ds.PatientID = patient_id

        if patient_name is not None:
            ds.PatientName = patient_name

        return (ds.PatientID, ds.PatientName)

    def anonymize_folder(self, folder, *args, **kwargs):
        if not os.path.isdir(folder):
            raise ValueError(f"Invalid folder: {folder}")

        callback = kwargs.pop('callback', None)
        if callback is not None and not callable(callback):
            raise ValueError("callback must be callable function")

        for root, _, files in os.walk(folder):
            for filename in files:
                filepath = os.path.join(root, filename)
                ds = pydicom.dcmread(filepath)
                self.anonymize_dataset(ds, *args, **kwargs)

                # Allow to manipulate the dataset before saving it to disk
                if callback:
                    callback(ds)

                ds.save_as(filepath)

        return True

    def generate_pseudonym(
        self,
        length=12,
        prefix="",
        suffix="",
        random_string=True,
        uppercase=True
    ):
        pseudonym = None
        while True:
            chars = string.ascii_lowercase + string.digits
            if random_string:
                pseudonym = ''.join(random.choice(chars) for _ in range(length))
                if uppercase:
                    pseudonym = pseudonym.upper()
            else:
                pseudonym = str(len(self.generated_pseudonyms) + 1).zfill(length)
            pseudonym = prefix + pseudonym + suffix
            if not pseudonym in self.generated_pseudonyms:
                self.generated_pseudonyms.append(pseudonym)
                return pseudonym
