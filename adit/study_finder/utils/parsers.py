import csv
from django.conf import settings
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser
from ..models import StudyFinderQuery


class QueriesParserError(Exception):
    pass


class QueriesParser(BaseParser):
    def parse(self, csv_file):
        queries = []
        errors = []
        reader = csv.DictReader(csv_file, delimiter=self._delimiter)
        for num, data in enumerate(reader):
            study_date_start, study_date_end = self.parse_date_range(
                data.get("Study Date", "")
            )
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
                query.full_clean(exclude=["job"])
            except ValidationError as err:
                pass

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
