import csv
from adit.core.utils.parsers import BaseParser, ParserError
from ..models import StudyFinderQuery
from ..serializers import StudyFinderQuerySerializer


class QueriesParser(BaseParser):
    field_to_column_mapping = {
        "row_id": "Row ID",
        "patient_id": "Patient ID",
        "patient_name": "Patient Name",
        "patient_birth_date": "Birth Date",
        "study_date_start": "From",
        "study_date_end": "Until",
        "modalities": "Modalities",
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
                    "study_date_start": row_data.get("From", ""),
                    "study_date_end": row_data.get("Until", ""),
                    "modalities": row_data.get("Modalities", ""),
                }
            )

        serializer = StudyFinderQuerySerializer(data=data, many=True)
        if not serializer.is_valid():
            raise ParserError(self.build_error_message(data, serializer.errors))

        return [StudyFinderQuery(**item) for item in serializer.validated_data]
