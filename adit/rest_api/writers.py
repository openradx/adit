from typing import Type
from io import BufferedWriter

from pydicom import DataElement
from pydicom.filewriter import dcmwrite, write_file_meta_info
from pydicom.uid import RLELossless
import json


class ElementWriter():
    fpath: str = None
    boundary: str = None
    content_type: str = None


class DicomDataElementWriter(ElementWriter):
    def __init__(
        self, fpath: str, boundary: str
    ) -> None:
        super().__init__()
        self.fpath = fpath
        self.boundary = boundary.encode('ascii')
        self.content_type = b"application/dicom"

    def write_ds(
        self, ds: Type[DataElement]
    ) -> tuple:
        with open(self.fpath, "ab") as file:
            self._write_boundary(file)
            self._write_header(file)
            if ds.is_little_endian:
                self._write_part(file, ds)
        return self.fpath, self.boundary

    def _write_part(
        self, file: Type[BufferedWriter], ds: Type[DataElement]
    ) -> None:
        dcmwrite(file, ds, write_like_original=False)
        file.write(b"\r\n")

    def _write_header(
        self, file: Type[BufferedWriter]
    ) -> None:
        content = b"Content-Type: " + self.content_type
        bound = b"; boundary=" + self.boundary
        header = content+bound

        file.write(header)
        file.write(b"\r\n")
        file.write(b"\r\n")

    def _write_boundary(
        self, file: Type[BufferedWriter]
    ) -> None:
        file.write(b"\r\n")
        file.write(b"--" + self.boundary + b"\r\n")


class DicomJsonDataElementWriter(ElementWriter):
    def __init__(
        self, fpath: str, boundary: str
    ) -> None:
        super().__init__()
        self.fpath = fpath
        self.content_type = "application/dicom+json"
        self.list = []
        
    def write_ds(
        self, ds: Type[DataElement]
    ) -> None:
        json_meta = ds.file_meta.to_json_dict()
        self.list.append(json_meta)
        with open(self.fpath, "w") as file:
            json.dump(self.list, file)
        return self.fpath, self.boundary


class XMLDataElementWriter(ElementWriter):
    def __init__(self, file, boundary):
        super().__init__()
        self.file = file
        self.boundary = boundary
        self.content_type = "application/dicom+xml"

    def write(self, ds):
        self.file.write("--" + self.boundary + "\r\n")
        self._write_header(self.file, content_type=self.content_type)
        write_file_meta_info(self.file, ds.file_meta)


class JPEGDataElementWriter(ElementWriter):
    def __init__(self, file, boundary):
        super().__init__()
        self.file = file
        self.boundary = boundary
        self.content_type = "image/dicom+jpeg"

    def write(self, ds):
        ds.compress(RLELossless, encoding_plugin='pylibjpeg')
        self.file.write(b"--" + self.boundary + b"\r\n")
        self._write_header(self.file, content_type=self.content_type)
        self.file.write(ds.PixelData)
        self.file.write(b"\r\n")