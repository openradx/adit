from dataclasses import dataclass


@dataclass
class Report:
    pacs_aet: str
    pacs_name: str
    patient_id: str
    study_uid: str
    accession_number: str
    study_description: str
    study_datetime: str
    series_uid: str
    modalities: list[str]
    instance_uid: str
    references: list[str]
    content: str
