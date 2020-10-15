import csv
import re
from datetime import datetime
from django.core.exceptions import ValidationError
from ..models import BatchTransferRequest


def parse_int(value):
    if value is not None and value.isdigit():
        return int(value.strip())
    return value


def parse_string(value):
    if value is not None:
        return value.strip()
    return value


def parse_name(value):
    if value is not None:
        return re.sub(r"\s*,\s*", "^", value.strip())
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
    label = BatchTransferRequest._meta.get_field(field_id).verbose_name
    camelcase = "".join(x for x in label.title() if not x.isspace())
    if camelcase == "PatientId":
        camelcase = "PatientID"
    return camelcase


def build_request_error(message_dict, num, row_key):
    general_errors = []
    field_errors = []

    if not isinstance(row_key, int):
        row_key = None

    if row_key is not None:
        general_errors.append(f"Invalid request with RowKey {row_key}:")
    else:
        general_errors.append(f"Invalid request #{num + 1}:")

    for field_id, messages in message_dict.items():
        if field_id == "__all__":
            for message in messages:
                general_errors.append(message)
        else:
            field_label = get_field_label(field_id)
            field_errors.append(f"{field_label}: {', '.join(messages)}")

    return "\n".join(general_errors) + "\n" + "\n".join(field_errors) + "\n"


class ParsingError(Exception):
    pass


class RequestsParser:  # pylint: disable=too-few-public-methods
    def __init__(self, delimiter, date_formats):
        self._delimiter = delimiter
        self._date_formats = date_formats

    def parse(self, csv_file):
        requests = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for num, data in enumerate(reader):
            request = BatchTransferRequest(
                row_key=parse_int(data.get("RowKey")),
                patient_id=parse_string(data.get("PatientID")),
                patient_name=parse_name(data.get("PatientName")),
                patient_birth_date=parse_date(
                    data.get("PatientBirthDate"), self._date_formats
                ),
                accession_number=parse_string(data.get("AccessionNumber")),
                study_date=parse_date(data.get("StudyDate"), self._date_formats),
                modality=parse_string(data.get("Modality")),
                pseudonym=parse_string(data.get("Pseudonym")),
            )

            try:
                request.full_clean(exclude=["job"])
            except ValidationError as err:
                request_error = build_request_error(
                    err.message_dict, num, request.row_key
                )
                errors.append(request_error)

            requests.append(request)

        row_keys = set()
        duplicates = set()
        for request in requests:
            row_key = request.row_key
            if row_key is not None and isinstance(row_key, int):
                if row_key not in row_keys:
                    row_keys.add(row_key)
                else:
                    duplicates.add(row_key)

        if len(duplicates) > 0:
            ds = ", ".join(str(i) for i in duplicates)
            errors.insert(0, f"Duplicate RowKey: {ds}")

        if len(errors) > 0:
            error_details = "\n".join(errors)
            raise ParsingError(error_details)

        return requests
