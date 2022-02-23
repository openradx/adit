from adit.core.parsers import BatchFileParser
from .serializers import BatchQueryTaskSerializer

mapping = {
    "patient_id": "PatientID",
    "patient_name": "PatientName",
    "patient_birth_date": "PatientBirthDate",
    "accession_number": "AccessionNumber",
    "study_date_start": "From",
    "study_date_end": "Until",
    "modalities": "Modality",
    "pseudonym": "Pseudonym",
    "series_description": "SeriesDescription",
}


class BatchQueryFileParser(BatchFileParser):
    serializer_class = BatchQueryTaskSerializer

    def __init__(self) -> None:
        super().__init__(mapping)
