import io
import logging
from typing import AsyncIterator

from django.http import HttpRequest
from pydicom import Dataset
from pydicom.errors import InvalidDicomError
from rest_framework.exceptions import NotAcceptable
from rest_framework.parsers import BaseParser

from adit.core.utils.dicom_utils import read_dataset

logger = logging.getLogger(__name__)


class StowMultipartApplicationDicomParser(BaseParser):
    media_type = "multipart/related; type=application/dicom"

    async def parse(
        self, stream, media_type=None, parser_context=None
    ) -> AsyncIterator[Dataset | None]:
        if parser_context is None:
            raise ValueError("Parser context is required")

        request = parser_context["request"]

        async for ds in self._parse_request_in_chunks(request):
            yield ds

    async def _parse_request_in_chunks(
        self, request: HttpRequest, chunk_size: int = 8192
    ) -> AsyncIterator[Dataset | None]:
        try:
            media_type: str | None = request.content_type
            assert media_type is not None, "Content-Type header is required"
            boundary: bytes = b"--" + media_type.split("boundary=")[1].strip('"').encode()
        except (IndexError, AssertionError):
            raise NotAcceptable("Invalid multipart request with no boundary")

        part: bytes = bytes()
        while True:
            chunk: bytes = request.read(chunk_size)

            if not chunk:
                if part:
                    ds = await self.get_dicom_from_part(part)
                    if ds is not None:
                        yield ds
                break

            if boundary in chunk:
                idx = chunk.index(boundary)
                part += chunk[:idx]

                if part:
                    ds = await self.get_dicom_from_part(part)
                    if ds is not None:
                        yield ds

                part = bytes()
                part += chunk[idx + len(boundary) :]

            else:
                part += chunk

    async def get_dicom_from_part(self, part: bytes) -> Dataset | None:
        if part in (b"", b"--", b"\r\n") or part.startswith(b"--\r\n"):
            return None

        idx_start = part.index(b"\r\n\r\n")
        try:
            idx_end = part.rindex(b"\r\n")
        except ValueError:
            idx_end = -1
        if idx_start > -1:
            content = part[idx_start + 4 : idx_end].strip()
            try:
                ds = read_dataset(io.BytesIO(content))
                return ds
            except InvalidDicomError:
                return None

        return None
