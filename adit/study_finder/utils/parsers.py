from adit.core.utils.parsers import BaseParser
from ..serializers import StudyFinderQuerySerializer


class QueriesParser(BaseParser):
    serializer_class = StudyFinderQuerySerializer
    field_to_column_mapping = {
        "row_id": "Row ID",
        "patient_id": "Patient ID",
        "patient_name": "Patient Name",
        "patient_birth_date": "Birth Date",
        "study_date_start": "From",
        "study_date_end": "Until",
        "modalities": "Modalities",
    }
