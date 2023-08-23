import json
import os
from io import BytesIO

from pydicom import Dataset
from rest_framework.renderers import BaseRenderer

from adit.core.utils.dicom_utils import read_dataset, write_dataset


class QidoApplicationDicomJsonRenderer(BaseRenderer):
    media_type = "application/dicom+json"
    format = "json"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data)


class DicomWebWadoRenderer(BaseRenderer):
    media_type: str
    format: str
    subtype: str | None
    boundary: str | None
    charset: str | None
    mode: str | None

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


class WadoMultipartApplicationDicomRenderer(DicomWebWadoRenderer):
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
        # We have to write the dataset with write_like_original=False to
        # make sure that DICOMweb Client can read it as it doesn't use
        # the force option of dcmread internally.
        # https://github.com/ImagingDataCommons/dicomweb-client/issues/89
        # TODO: Maybe we should check if there is a better way to write the DICOM
        # file (how about the metadata?!).
        write_dataset(ds, self.stream, write_like_original=False)
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
            ds = read_dataset(file_path)
            self.write_ds(ds)
            os.remove(file_path)
        self.end_stream()
        os.rmdir(folder_path)
        return self.stream


class WadoApplicationDicomJsonRenderer(DicomWebWadoRenderer):
    media_type = "application/dicom+json"
    format = "json"
    mode = "metadata"

    def start_file_meta_list(self):
        self.file_meta_list = []

    def append_file_meta(self, ds: Dataset):
        if hasattr(ds, "PixelData"):
            del ds.PixelData
        json_meta = ds.to_json_dict()
        self.file_meta_list.append(json_meta)

    def render(self, data, accepted_media_type=None, renderer_context=None):
        self.start_file_meta_list()
        for file in os.listdir(data["folder_path"]):
            file_path = data["folder_path"] / file
            ds = read_dataset(file_path)
            self.append_file_meta(ds)
            os.remove(file_path)
        os.rmdir(data["folder_path"])
        return json.dumps(self.file_meta_list)


class StowApplicationDicomJsonRenderer(BaseRenderer):
    media_type = "application/dicom+json"
    format = "json"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        result_list = []
        for ds in data:
            result_list.append(ds.to_json_dict())

        # TODO: We currently don't respect the DICOM standard here. We should respect
        # https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.5.3-1
        # and evaluate the response status codes correctly.
        if len(result_list) == 1:
            return json.dumps(result_list[0])
        return json.dumps(result_list)
