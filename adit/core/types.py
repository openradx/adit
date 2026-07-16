from datetime import date, time
from typing import Literal, TypedDict

from adit.core.models import DicomTask


class DicomLogEntry(TypedDict):
    level: Literal["Info", "Warning"]
    title: str
    message: str


class ProcessingResult(TypedDict):
    status: DicomTask.Status
    message: str
    log: str


class StudyParams(TypedDict):
    study_date: date
    study_time: time
    study_modalities: list[str]
    pseudonym: str | None
    trial_protocol_id: str | None
    trial_protocol_name: str | None
