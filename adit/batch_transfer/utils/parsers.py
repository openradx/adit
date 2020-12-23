import csv
from adit.core.utils.parsers import BaseParser, ParserError
from ..models import BatchTransferRequest
from ..serializers import BatchTransferRequestSerializer


class RequestsParser(BaseParser):  # pylint: disable=too-few-public-methods
    field_to_column_mapping = {
        "row_id": "Row ID",
        "patient_id": "Patient ID",
        "patient_name": "Patient Name",
        "patient_birth_date": "Birth Date",
        "accession_number": "Accession Number",
        "study_date": "Study Date",
        "modality": "Modality",
        "pseudonym": "Pseudonym",
    }

    def parse(self, csv_file):
        data = []
        reader = csv.DictReader(csv_file, delimiter=self.delimiter)
        for row_data in reader:
            data.append(
                {
                    "row_id": row_data.get("Row ID", ""),
                    "patient_id": row_data.get("Patient ID", ""),
                    "patient_name": row_data.get("Patient Name", ""),
                    "patient_birth_date": row_data.get("Birth Date", ""),
                    "accession_number": row_data.get("Accession Number", ""),
                    "study_date": row_data.get("Study Date", ""),
                    "modality": row_data.get("Modality", ""),
                    "pseudonym": row_data.get("Pseudonym"),
                }
            )

        serializer = BatchTransferRequestSerializer(data=data, many=True)
        if not serializer.is_valid():
            raise ParserError(
                self.build_error_message(serializer.errors, serializer.data)
            )

        return [BatchTransferRequest(**item) for item in serializer.validated_data]
