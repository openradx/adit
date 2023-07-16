from dataclasses import dataclass
from datetime import date, time


@dataclass
class Report:
    pacs_aet: str
    pacs_name: str
    patient_id: str
    study_uid: str
    accession_number: str
    study_description: str
    study_date: date
    study_time: time
    series_uid: str
    modalities: list[str]
    instance_uid: str
    reference_uids: list[str]
    content: str
