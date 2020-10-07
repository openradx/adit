import csv
import re
from datetime import datetime


class ParsingError(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.message = message
        self.errors = errors

    def __str__(self):
        errors = "\n".join(self.errors)
        return self.message + "\n" + errors


class RequestParser:  # pylint: disable=too-few-public-methods
    def __init__(self, delimiter, date_formats):
        self._delimiter = delimiter
        self._date_formats = date_formats

        self._errors = []
        self._row_keys = set()
        self._patient_ids = dict()
        self._pseudonyms = dict()

    def parse(self, csv_file):
        self._errors = []
        self._row_keys = set()
        self._patient_ids = dict()
        self._pseudonyms = dict()
        requests = []

        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for i, row in enumerate(reader):
            request = self._extract_request(row, i)
            requests.append(request)

        if len(self._errors) > 0:
            raise ParsingError("Invalid format of CSV file.", self._errors)

        return requests

    def _extract_request(self, row, i):
        row_key = row.get("RowKey", "").strip()
        row_key = self._clean_row_key(row_key, i)
        patient_id = row.get("PatientID", "").strip()
        patient_id = self._clean_patient_id(patient_id, i)
        patient_name = row.get("PatientName", "").strip()
        patient_name = self._clean_patient_name(patient_name, i)
        patient_birth_date = row.get("PatientBirthDate", "").strip()
        patient_birth_date = self._clean_patient_birth_date(patient_birth_date, i)
        accession_number = row.get("AccessionNumber", "").strip()
        accession_number = self._clean_accession_number(accession_number, i)
        study_date = row.get("StudyDate", "").strip()
        study_date = self._clean_study_date(study_date, i)
        modality = row.get("Modality", "").strip()
        modality = self._clean_modality(modality, i)
        pseudonym = row.get("Pseudonym", "").strip()
        pseudonym = self._clean_pseudonym(pseudonym, i)

        request = {
            "RowKey": row_key,
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
            "AccessionNumber": accession_number,
            "StudyDate": study_date,
            "Modality": modality,
            "Pseudonym": pseudonym,
        }

        return self._clean_request(request, i)

    def _clean_row_key(self, row_key, i):
        if not row_key:
            self._errors.append(f"Missing RowKey in row {i}.")
        elif not row_key.isdigit():
            self._errors.append(f"Invalid RowKey in row {i}. Must be a digit.")
        else:
            r_id = int(row_key)
            if r_id in self._row_keys:
                self._errors.append(f"Duplicate RowKey in row {i}.")
            else:
                self._row_keys.add(r_id)
                return r_id
        return row_key

    def _clean_patient_id(self, patient_id, i):
        if len(patient_id) > 64:
            self._errors.append(f"Invalid PatientID in row {i}. Maximum 64 characters.")
        return patient_id

    def _clean_patient_name(self, patient_name, i):
        name = re.sub(r",\s*", "^", patient_name)
        if len(name) > 324:
            self._errors.append(
                f"Invalid PatientName in row {i}. Maximum 324 characters."
            )
            return patient_name

        return name

    def _clean_patient_birth_date(self, patient_birth_date, i):
        if patient_birth_date:
            date = self._parse_date(patient_birth_date)
            if date:
                return date

            self._errors.append(f"Invalid date format of PatientBirthDate in row {i}.")
        return patient_birth_date

    def _clean_accession_number(self, accession_number, i):
        if len(accession_number) > 16:
            self._errors.append(
                f"Invalid AccessionNumber in row {i}. Maximum 16 characters."
            )
        return accession_number

    def _clean_study_date(self, study_date, i):
        if study_date:
            date = self._parse_date(study_date)
            if date:
                return date

            self._errors.append(f"Invalid date format of StudyDate in row {i}.")
        return study_date

    def _clean_modality(self, modality, i):
        if len(modality) > 16:
            self._errors.append(f"Invalid Modality in row {i}. Maximum 16 characters.")
        return modality

    def _clean_pseudonym(self, pseudonym, i):
        pseudo = re.sub(r",\s*", "^", pseudonym)
        if len(pseudo) > 64:
            self._errors.append(f"Invalid Pseudonym in row {i}. Maximum 64 characters.")
            return pseudonym

        return pseudo

    def _parse_date(self, date_str):
        date = None
        for date_format in self._date_formats:
            try:
                date = datetime.strptime(date_str, date_format)
                break
            except ValueError:
                pass
        return date

    def _clean_request(self, request, i):
        patient_id = request["PatientID"]
        patient_name = request["PatientName"]
        birth_date = request["PatientBirthDate"]
        pseudonym = request["Pseudonym"]

        # When both PatientID and PatientName / PatientBirthDate are
        # present then they must never mix up
        if patient_id and (patient_name or birth_date):
            descriptor = f"{patient_id}_{patient_name}_{birth_date}"
            if patient_id in self._patient_ids:
                v = self._patient_ids[patient_id]
                if v and v != descriptor:
                    msg = (
                        "The same PatientID was also given for a different "
                        f"PatientName / PatientBirthDate in row {i}."
                    )
                    self._errors.append(msg)
            else:
                self._patient_ids[patient_id] = descriptor

        if pseudonym:
            # Only one pseudonym allowed per patient
            # This can still go wrong when patient data is mixed with
            # only an accession number per request, but this can only be
            # found out while real data is fetched
            descriptor = f"{patient_id}_{patient_name}_{birth_date}"
            if pseudonym in self._pseudonyms:
                v = self._pseudonyms[pseudonym]
                if v and v != descriptor:
                    msg = f"Pseudonym already used for another patient in row {i}."
                    self._errors.append(msg)
            else:
                self._pseudonyms[pseudonym] = descriptor

        # If an AccessionNumber is present we don't need anything else.
        if request.get("AccessionNumber"):
            return request

        # If PatientName is present then PatientBirthDate must be
        # also present too and the other way around
        if patient_name and not birth_date:
            msg = (
                "When PatientName is present then PatientBirthDate"
                f"must also be present in row {i}."
            )
            self._errors.append(msg)
        elif birth_date and not patient_name:
            msg = (
                "When PatientBirthDate is present then PatientName"
                f"must also be present in row {i}."
            )
            self._errors.append(msg)

        # The patient must somehow be identifiable
        if not (patient_id or patient_name and birth_date):
            msg = (
                "AccessionNumber or PatientID or PatientName and "
                f"PatientBirthDate must be present in row {i}."
            )
            self._errors.append(msg)

        return request
