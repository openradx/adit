import json
import os
from io import BytesIO
from typing import Optional

from pydicom import Dataset, dcmread, dcmwrite
from rest_framework.renderers import BaseRenderer


class DicomWebWadoRenderer(BaseRenderer):
    media_type: str
    subtype: Optional[str]
    boundary: Optional[str]
    charset: Optional[str]
    mode: Optional[str]

    @property
    def content_type(self) -> str:
        str = f"{self.media_type}"
        if hasattr(self, "subtype"):
            str += f"; type={self.subtype}"
        if hasattr(self, "boundary"):
            str += f"; boundary={self.boundary}"
        if hasattr(self, "charset"):
            str += f"; charset={self.charset}"
        return str


class MultipartApplicationDicomRenderer(DicomWebWadoRenderer):
    media_type = "multipart/related; type=application/dicom"
    format = "multipart"

    subtype: str = "application/dicom"
    boundary: str = "adit-boundary"
    charset: str = "utf-8"
    mode: str = "bulk"

    def start_stream(self):
        self.stream = BytesIO()

    def end_stream(self):
        self.stream.write(b"--")
        self.stream.write(self.boundary.encode("utf-8"))
        self.stream.write(b"--")
        self.stream.seek(0)

    def write_ds(self, ds: Dataset):
        self._write_boundary()
        self._write_header()
        if ds.is_little_endian:
            self._write_part(ds)

    def _write_part(self, ds: Dataset) -> None:
        dcmwrite(self.stream, ds, write_like_original=False)
        self.stream.write(b"\r\n")

    def _write_header(self) -> None:
        self.stream.write(b"Content-Type: " + self.subtype.encode("utf-8"))
        self.stream.write(b"\r\n")
        self.stream.write(b"\r\n")

    def _write_boundary(self) -> None:
        self.stream.write(b"\r\n")
        self.stream.write(b"--" + self.boundary.encode("utf-8") + b"\r\n")

    def render(self, data, accepted_media_type=None, renderer_context=None):
        folder_path = data["folder_path"]
        self.start_stream()
        for file in os.listdir(folder_path):
            file_path = folder_path / file
            ds = dcmread(file_path)
            self.write_ds(ds)
            os.remove(file_path)
        self.end_stream()
        os.rmdir(folder_path)
        return self.stream


class ApplicationDicomJsonRenderer(DicomWebWadoRenderer):
    media_type = "application/dicom+json"
    format = "json"

    mode = "metadata"

    def start_file_meta_list(self):
        self.file_meta_list = []

    def append_file_meta(self, ds: Dataset):
        json_meta = ds.file_meta.to_json_dict()
        self.file_meta_list.append(json_meta)

    def render(self, data, *args, **kwargs):
        self.start_file_meta_list()
        for file in os.listdir(data["folder_path"]):
            file_path = data["folder_path"] / file
            ds = dcmread(file_path)
            self.append_file_meta(ds)
            os.remove(file_path)
        os.rmdir(data["folder_path"])
        return json.dumps(self.file_meta_list)
