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
