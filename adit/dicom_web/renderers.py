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


class MultipartRenderer(BaseRenderer):
    media_type: str
    format: str
    subtype: str | None = None
    boundary: str = "default-boundary"
    charset: str | None = None

    async def render(self, items: AsyncIterator[BytesIO | Dataset]) -> AsyncIterator[bytes]:
        try:
            async for item in items:
                yield self._instance_stream(item)
        except Exception as err:
            yield self._error_stream(err)
        yield self._end_stream()

    def _instance_stream(self, item: BytesIO | Dataset) -> bytes:
        stream = BytesIO()
        # boundary
        stream.write(b"\r\n")
        stream.write(b"--" + self.boundary.encode("utf-8") + b"\r\n")
        # header
        stream.write(b"Content-Type: " + self.subtype.encode("utf-8"))  # type: ignore
        stream.write(b"\r\n")
        stream.write(b"\r\n")
        # instance
        self._write_item(item, stream)
        stream.write(b"\r\n")
        return stream.getvalue()

    def _write_item(self, item: BytesIO | Dataset, stream: BytesIO):
        raise NotImplementedError("Subclasses must implement `_write_item`.")

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
        stream.write(f"Error: {err}\r\n".encode("utf-8"))
        stream.write(b"\r\n")
        return stream.getvalue()

    def _end_stream(self) -> bytes:
        stream = BytesIO()
        stream.write(b"--")
        stream.write(self.boundary.encode("utf-8"))
        stream.write(b"--")
        return stream.getvalue()


class WadoMultipartApplicationDicomRenderer(MultipartRenderer):
    media_type = "multipart/related; type=application/dicom"
    format = "multipart"
    subtype: str = "application/dicom"
    boundary: str = "adit-boundary"
    charset: str = "utf-8"

    @property
    def content_type(self) -> str:
        return f"{self.media_type}; boundary={self.boundary}"

    def _write_item(self, item: Dataset, stream: BytesIO):
        write_dataset(item, stream)


class WadoMultipartApplicationNiftiRenderer(MultipartRenderer):
    media_type = "multipart/related; type=application/octet-stream"
    format = "multipart"
    subtype: str = "application/octet-stream"
    boundary: str = "nifti-boundary"
    charset: str = "utf-8"

    @property
    def content_type(self) -> str:
        return f"{self.media_type}; boundary={self.boundary}"

    def render(self, images: AsyncIterator[tuple[str, BytesIO]]) -> AsyncIterator[bytes]:
        async def streaming_content():
            first_part = True
            async for filename, file_content in images:
                # For multipart format, we need to start with boundary
                if first_part:
                    yield f"--{self.boundary}\r\n".encode()
                    first_part = False
                else:
                    yield f"\r\n--{self.boundary}\r\n".encode()

                # Add headers for this part
                yield "Content-Type: application/octet-stream\r\n".encode()
                yield f'Content-Disposition: attachment; filename="{filename}"\r\n\r\n'.encode()

                # Add content
                yield file_content.getvalue()

            # End the multipart message with a final boundary
            yield f"\r\n--{self.boundary}--\r\n".encode()

        return streaming_content()


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
