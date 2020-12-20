import csv
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser
from ..models import BatchTransferRequest

field_to_column_mapping = {
    "row_number": "Row",
    "patient_id": "Patient ID",
    "patient_name": "Patient Name",
    "patient_birth_date": "Birth Date",
    "accession_number": "Accession Number",
    "study_date": "Study Date",
    "modality": "Modality",
    "pseudonym": "Pseudonym",
}


class RequestsParserError(Exception):
    pass


class RequestsParser(BaseParser):  # pylint: disable=too-few-public-methods
    def parse(self, csv_file):
        requests = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for request_number, data in enumerate(reader):
            request = BatchTransferRequest(
                row_number=self.parse_int(data.get("Row", "")),
                patient_id=self.parse_string(data.get("Patient ID", "")),
                patient_name=self.parse_name(data.get("Patient Name", "")),
                patient_birth_date=self.parse_date(data.get("Birth Date", "")),
                accession_number=self.parse_string(data.get("Accession Number", "")),
                study_date=self.parse_date(data.get("Study Date", "")),
                modality=self.parse_string(data.get("Modality", "")),
                pseudonym=self.parse_string(data.get("Pseudonym", "")),
            )

            try:
                request.full_clean(exclude=["job"])
            except ValidationError as err:
                request_error = _build_request_error(
                    err.message_dict, request.row_number, request_number
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
            errors.insert(0, f"Duplicate 'Row' number: {ds}")

        if len(errors) > 0:
            error_details = "\n".join(errors)
            raise RequestsParserError(error_details)

        return requests


def _build_request_error(message_dict, row_number, request_number):
    general_errors = []
    field_errors = []

    if not isinstance(row_number, int):
        row_number = None

    if row_number is not None:
        general_errors.append(f"Invalid request [Row {row_number}]:")
    else:
        general_errors.append(f"Invalid request [#{request_number + 1}]:")

    for field_id, messages in message_dict.items():
        if field_id == "__all__":
            for message in messages:
                general_errors.append(message)
        else:
            column_label = field_to_column_mapping[field_id]
            field_errors.append(f"{column_label}: {', '.join(messages)}")

    return "\n".join(general_errors) + "\n" + "\n".join(field_errors) + "\n"
