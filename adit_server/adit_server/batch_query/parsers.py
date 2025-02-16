from adit_server.core.parsers import BatchFileParser
from adit_server.core.utils.dicom_utils import person_name_to_dicom

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


class BatchQueryFileParser(BatchFileParser[BatchQueryTask]):
    serializer_class = BatchQueryTaskSerializer

    def __init__(self) -> None:
        super().__init__(mapping)

    def transform_value(self, field: str, value: str) -> str | list[str] | None:
        if field in ["patient_birth_date", "study_date_start", "study_date_end"]:
            if not value:
                return None

        if field in ["modalities", "series_numbers"]:
            return [x.strip() for x in value.split(",") if x.strip()]

        if field == "patient_name":
            return person_name_to_dicom(value)

        return value
