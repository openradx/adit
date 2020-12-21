import csv
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser, ParserError
from ..models import BatchTransferRequest


class RequestsParser(BaseParser):  # pylint: disable=too-few-public-methods
    item_name = "request"
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

    def parse(self, csv_file):
        requests = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self.delimiter)
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
                request_error = self.build_item_error(
                    err.message_dict, request.row_number, request_number
                )
                errors.append(request_error)

            requests.append(request)

        row_numbers = [request.row_number for request in requests]
        duplicates = self.find_duplicates(row_numbers)

        if len(duplicates) > 0:
            ds = ", ".join(str(i) for i in duplicates)
            errors.insert(0, f"Duplicate 'Row' number: {ds}")

        if len(errors) > 0:
            error_details = "\n".join(errors)
            raise ParserError(error_details)

        return requests
