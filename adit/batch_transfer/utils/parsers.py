import csv
from datetime import datetime
from django.core.exceptions import ValidationError
from adit.main.validators import validate_pseudonym
from ..models import BatchTransferRequest


def parse_int(value):
    if value is not None and value.isdigit():
        return int(value.strip())
    return value


def parse_string(value):
    if value is not None:
        return value.strip()
    return value


def parse_date(value, date_formats):
    if value is not None:
        for date_format in date_formats:
            try:
                return datetime.strptime(value.strip(), date_format)
            except ValueError:
                pass
    return value


def get_field_label(field_id):
    return BatchTransferRequest._meta.get_field(field_id).verbose_name


def make_camelcase(s):
    "".join(x for x in s.title() if not x.isspace())


def extract_request_errors(message_dict):
    errors = []
    for field_id, messages in message_dict:
        field_label = get_field_label(field_id)
        errors.append(f"{field_label}: {', '.join(messages)}")
    return errors


class ParsingError(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.message = message
        self.errors = errors

    def __str__(self):
        errors = "\n".join(self.errors)
        return self.message + "\n" + errors


class RequestsParser:  # pylint: disable=too-few-public-methods
    def __init__(self, delimiter, date_formats):
        self._delimiter = delimiter
        self._date_formats = date_formats

    def parse(self, csv_file):
        requests = []
        errors = {}

        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for row, data in enumerate(reader):
            request = self._parse_request(data)

            try:
                request.full_clean()
            except ValidationError as err:
                request_errors = extract_request_errors(err.message_dict)
                errors[row] = request_errors

            requests.append(request)

        # TODO check for unique row keys

        if len(errors) > 0:
            raise ParsingError("Invalid format of CSV file.", errors)

        return requests

    def _parse_request(self, data):
        return BatchTransferRequest(
            row_key=parse_int(data.get("RowKey")),
            patient_id=parse_string(data.get("PatientID")),
            patient_name=parse_string(data.get("PatientName")),
            patient_birth_date=parse_date(
                data.get("PatientBirthDate"), self._date_formats
            ),
            accession_number=parse_string(data.get("AccessionNumber")),
            study_date=parse_date(data.get("StudyDate"), self._date_formats),
            modality=parse_string(data.get("Modality")),
            pseudonym=parse_string(data.get("Pseudonym")),
        )
