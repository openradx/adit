from typing import Type
from .writers import (
    ElementWriter, 
    DicomDataElementWriter, 
    DicomJsonDataElementWriter,
)


class DicomWebFileFormat():
    content_type: str = None
    multipart: bool = None
    mode: str = None
    mode_default: bool = None
    writer: Type[ElementWriter] = None

class ApplicationDicomJson(DicomWebFileFormat):
    content_type = "application/dicom+json"
    multipart = False
    mode = "meta"
    mode_default = True
    writer = DicomJsonDataElementWriter

class ApplicationDicom(DicomWebFileFormat):
    content_type = "application/dicom"
    multipart = True
    mode = "bulk"
    mode_default = True
    writer = DicomDataElementWriter

