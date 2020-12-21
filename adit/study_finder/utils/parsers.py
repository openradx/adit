import csv
from django.conf import settings
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser, ParserError
from ..models import StudyFinderQuery


class QueriesParser(BaseParser):
    item_name = "query"
    field_to_column_mapping = {
        "row_number": "Row",
        "patient_id": "Patient ID",
        "patient_name": "Patient Name",
        "patient_birth_date": "Birth Date",
        "study_date": "Study Date",
        "modalities": "Modalities",
    }

    def parse(self, csv_file):
        queries = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self.delimiter)
        for query_number, data in enumerate(reader):
            error_dict = {}
            study_date_start = None
            study_date_end = None

            try:
                study_date_start, study_date_end = self.parse_date_range(
                    data.get("Study Date", "")
                )
            except ValueError as err:
                error_dict["study_date"] = str(err)

            query = StudyFinderQuery(
                row_number=self.parse_int(data.get("Row", "")),
                patient_id=self.parse_string(data.get("Patient ID", "")),
                patient_name=self.parse_name(data.get("Patient Name", "")),
                patient_birth_date=self.parse_date(data.get("Birth Date", "")),
                study_date_start=study_date_start,
                study_date_end=study_date_end,
                modalities=self.parse_modalities(data.get("Modalities", "")),
            )

            try:
                exclude = ["job"]
                if "study_date" in error_dict:
                    exclude += ["study_date_start", "study_date_end"]
                query.full_clean(exclude=exclude)
            except ValidationError as err:
                error_dict.update(err.message_dict)

            if error_dict:
                errors.append(
                    self.build_item_error(error_dict, query.row_number, query_number)
                )

            queries.append(query)

        row_numbers = [query.row_number for query in queries]
        duplicates = self.find_duplicates(row_numbers)

        if len(duplicates) > 0:
            ds = ", ".join(str(i) for i in duplicates)
            errors.insert(0, f"Duplicate 'Row' number: {ds}")

        if len(errors) > 0:
            error_details = "\n".join(errors)
            raise ParserError(error_details)

        return queries

    def parse_modalities(self, value):
        modalities = value.split(",")
        return map(str.strip, modalities)

    def parse_date_range(self, value):
        ranges = value.split(settings.DATE_RANGE_DELIMITER)

        if len(ranges) > 2:
            raise ValueError("Invalid date range (more than two date components).")

        if len(ranges) == 1:
            return ranges[0], None

        if len(ranges) == 2:
            return ranges[0], ranges[1]

        return None, None
