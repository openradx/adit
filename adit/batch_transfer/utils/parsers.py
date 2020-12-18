import csv
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser
from ..models import BatchTransferRequest


def get_field_label(field_id):
    label = BatchTransferRequest._meta.get_field(field_id).verbose_name
    camelcase = "".join(x for x in label.title() if not x.isspace())
    if camelcase == "PatientId":
        camelcase = "PatientID"
    return camelcase


def build_request_error(message_dict, num, row_number):
    general_errors = []
    field_errors = []

    if not isinstance(row_number, int):
        row_number = None

    if row_number is not None:
        general_errors.append(f"Invalid request with RowNumber {row_number}:")
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


class RequestsParserError(Exception):
    pass


class RequestsParser(BaseParser):  # pylint: disable=too-few-public-methods
    def parse(self, csv_file):
        requests = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for num, data in enumerate(reader):
            request = BatchTransferRequest(
                row_number=self.parse_int(data.get("RowNumber", "")),
                patient_id=self.parse_string(data.get("PatientID", "")),
                patient_name=self.parse_name(data.get("PatientName", "")),
                patient_birth_date=self.parse_date(data.get("PatientBirthDate", "")),
                accession_number=self.parse_string(data.get("AccessionNumber", "")),
                study_date=self.parse_date(data.get("StudyDate", "")),
                modality=self.parse_string(data.get("Modality", "")),
                pseudonym=self.parse_string(data.get("Pseudonym", "")),
            )

            try:
                request.full_clean(exclude=["job"])
            except ValidationError as err:
                request_error = build_request_error(
                    err.message_dict, num, request.row_number
                )
                errors.append(request_error)

            requests.append(request)

        row_numbers = set()
        duplicates = set()
        for request in requests:
            row_number = request.row_number
            if row_number is not None and isinstance(row_number, int):
                if row_number not in row_numbers:
                    row_numbers.add(row_number)
                else:
                    duplicates.add(row_number)

        if len(duplicates) > 0:
            ds = ", ".join(str(i) for i in duplicates)
            errors.insert(0, f"Duplicate RowNumber: {ds}")

        if len(errors) > 0:
            error_details = "\n".join(errors)
            raise RequestsParserError(error_details)

        return requests
