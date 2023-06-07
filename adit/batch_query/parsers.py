import re

from adit.core.parsers import BatchFileParser
from adit.core.utils.dicom_utils import person_name_to_dicom

from .models import BatchQueryTask
from .serializers import BatchQueryTaskSerializer

mapping = {
    "patient_id": "PatientID",
    "patient_name": "PatientName",
    "patient_birth_date": "PatientBirthDate",
    "accession_number": "AccessionNumber",
    "study_date_start": "From",
    "study_date_end": "Until",
    "modalities": "Modality",
    "study_description": "StudyDescription",
    "series_description": "SeriesDescription",
    "series_numbers": "SeriesNumber",
    "pseudonym": "Pseudonym",
}

dt_regex = re.compile(r"^(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}$")


class BatchQueryFileParser(BatchFileParser[BatchQueryTask]):
    serializer_class = BatchQueryTaskSerializer

    def __init__(self) -> None:
        super().__init__(mapping)

    def transform_value(self, field: str, value: str) -> str | list[str] | None:
        if field in ["patient_birth_date", "study_date_start", "study_date_end"]:
            if not value:
                return None

            m = dt_regex.match(value)
            if m:
                # Only extract the date as the DateField of the date field
                # will only parse a valid date without time.
                return m.group(1)

        if field in ["modalities", "series_numbers"]:
            values = value.split(",")
            values = map(str.strip, values)
            values = filter(len, values)
            return list(values)

        if field == "patient_name":
            return person_name_to_dicom(value)

        return value
