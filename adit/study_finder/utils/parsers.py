import csv
from django.conf import settings
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser
from ..models import StudyFinderQuery

field_to_column_mapping = {
    "row_number": "Row",
    "patient_id": "Patient ID",
    "patient_name": "Patient Name",
    "patient_birth_date": "Birth Date",
    "study_date": "Study Date",
    "modalities": "Modalities",
    "study_date": "Study Date",
    "study_description": "Study Description",
}


class QueriesParserError(Exception):
    pass


class QueriesParser(BaseParser):
    def parse(self, csv_file):
        queries = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for query_number, data in enumerate(reader):
            study_date_start = None
            study_date_end = None
            study_date_error = None
            try:
                study_date_start, study_date_end = self.parse_date_range(
                    data.get("Study Date", "")
                )
            except ValueError as err:
                study_date_error = str(err)

            query = StudyFinderQuery(
                row_number=self.parse_int(data.get("Row", "")),
                patient_id=self.parse_string(data.get("Patient ID", "")),
                patient_name=self.parse_name(data.get("Patient Name", "")),
                patient_birth_date=self.parse_date(data.get("Birth Date", "")),
                modalities=self.parse_modalities(data.get("Modalities", "")),
                study_date_start=study_date_start,
                study_date_end=study_date_end,
            )

            try:
                exclude = ["job", "study_date_start", "study_date_end"]
                query.full_clean(exclude=exclude)
            except ValidationError as err:
                message_dict = err.message_dict
                if study_date_error:
                    message_dict["study_date"] = study_date_error
                query_error = build_query_error(
                    err.message_dict, query.row_number, query_number
                )
                errors.append(query_error)

            queries.append(query)

    def parse_modalities(self, value):
        modalities = value.split(",")
        return map(str.strip, modalities)

    def parse_date_range(self, value):
        ranges = value.split(settings.DATE_RANGE_DELIMITER)

        d1 = None
        try:
            d1 = ranges[0]
        except IndexError:
            pass

        d2 = None
        try:
            d2 = ranges[1]
        except IndexError:
            pass

        return d1, d2


def build_query_error(message_dict, row_number, query_number):
    pass
