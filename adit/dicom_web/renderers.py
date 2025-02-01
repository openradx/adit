import json
from io import BytesIO
from typing import AsyncIterator

from pydicom import Dataset
from rest_framework.renderers import BaseRenderer

from adit.core.utils.dicom_utils import write_dataset


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

    async def render(self, images: AsyncIterator[Dataset]) -> AsyncIterator[bytes]:
        try:
            async for image in images:
                yield self._instance_stream(image)
        except Exception as err:
            yield self._error_stream(err)

        yield self._end_stream()

    def _instance_stream(self, ds: Dataset) -> bytes:
        stream = BytesIO()
        # boundary
        stream.write(b"\r\n")
        stream.write(b"--" + self.boundary.encode("utf-8") + b"\r\n")
        # header
        stream.write(b"Content-Type: " + self.subtype.encode("utf-8"))
        stream.write(b"\r\n")
        stream.write(b"\r\n")
        # instance
        if not ds.is_little_endian:
            # TODO: What to do with big endian? Can we convert it somehow? When does this happen?
            raise ValueError("Invalid dataset encoding. Must be little endian.")
        write_dataset(ds, stream)
        stream.write(b"\r\n")
        return stream.getvalue()

    def _error_stream(self, err: Exception) -> bytes:
        stream = BytesIO()
        # boundary
        stream.write(b"\r\n")
        stream.write(b"--" + self.boundary.encode("utf-8") + b"\r\n")
        # header
        stream.write(b"Content-Type: text/plain")
        stream.write(b"\r\n")
        stream.write(b"\r\n")
        # message
        stream.write(f"Error: Failed to fetch DICOM data: {err}\r\n".encode("utf-8"))
        stream.write(b"\r\n")
        return stream.getvalue()

    def _end_stream(self) -> bytes:
        stream = BytesIO()
        stream.write(b"--")
        stream.write(self.boundary.encode("utf-8"))
        stream.write(b"--")
        return stream.getvalue()


class WadoApplicationDicomJsonRenderer(DicomWebWadoRenderer):
    media_type = "application/dicom+json"
    format = "json"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        metadata = data["metadata"]
        return json.dumps(metadata)


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
