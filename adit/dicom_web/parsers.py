import io

import pydicom
from pydicom.errors import InvalidDicomError
from rest_framework.exceptions import NotAcceptable
from rest_framework.parsers import BaseParser


class StowMultipartApplicationDicomParser(BaseParser):
    media_type = "multipart/related; type=application/dicom"

    def parse(self, stream, media_type: str, parser_context=None):
        try:
            boundary = media_type.split("boundary=")[1]
        except IndexError:
            raise NotAcceptable("Invalid multipart request with no boundary")

        datasets = []
        parts = stream.read().split(b"--" + boundary.encode())
        for part in parts:
            part = part.strip()
            content = self._get_part_content(part)
            if content:
                try:
                    ds = pydicom.dcmread(io.BytesIO(content))
                    datasets.append(ds)
                except InvalidDicomError:
                    pass
        return {"datasets": datasets}

    def _get_part_content(self, part: bytes) -> bytes | None:
        if part in (b"", b"--", b"\r\n") or part.startswith(b"--\r\n"):
            return None
        idx_start = part.index(b"\r\n\r\n")
        try:
            idx_end = part.rindex(b"\r\n")
        except ValueError:
            idx_end = -1
        if idx_start > -1:
            return part[idx_start + 4 : idx_end]
        return None
