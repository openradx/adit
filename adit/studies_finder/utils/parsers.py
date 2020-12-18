import csv
from django.core.exceptions import ValidationError
from adit.core.utils.parsers import BaseParser
from ..models import StudiesFinderQuery


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
            query = StudiesFinderQuery(
                query_id=self.parse_int(data.get("Query ID", "")),
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
        ranges = value.split("-")

        if len(ranges) > 2:
            raise ValueError(f"Invalid date range format: {value}")

        d1 = None
        d2 = None
        if len(ranges) > 0:
            d1 = self.parse_date(ranges[0])
        if len(ranges) > 1:
            d2 = self.parse_date(ranges[1])

        return d1, d2
