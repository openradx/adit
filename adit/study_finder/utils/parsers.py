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
                query.full_clean(exclude=["job", "study_date_start", "study_date_end"])
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
        # We must validate the dates ourself as we use other fields in the model.

        is_date_range = settings.DATE_RANGE_DELIMITER in value
        ranges = value.split(settings.DATE_RANGE_DELIMITER)

        if len(ranges) > 2:
            raise ValueError("Invalid date range (more than two date components).")

        if len(ranges) == 1:
            if is_date_range:
                start_date = self.parse_date(ranges[0])
                if not start_date:
                    raise ValueError(f"Invalid date: {ranges[0]}")
                return start_date, None
            else:
                date = self.parse_date(ranges[0])
                if not date:
                    ...
                return date, date

        if len(ranges) == 2:
            start_date = self.parse_date(ranges[0])
            end_date = self.parse_date(ranges[1])
            ...
        


        check start < end

        return None, None
