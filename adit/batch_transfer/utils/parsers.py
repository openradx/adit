from adit.core.utils.parsers import BaseParser
from ..serializers import BatchTransferRequestSerializer


class RequestsParser(BaseParser):  # pylint: disable=too-few-public-methods
    serializer_class = BatchTransferRequestSerializer
    field_to_column_mapping = {
        "row_id": "Row ID",
        "patient_id": "Patient ID",
        "patient_name": "Patient Name",
        "patient_birth_date": "Birth Date",
        "accession_number": "Accession Number",
        "study_date": "Study Date",
        "modality": "Modality",
        "pseudonym": "Pseudonym",
    }
