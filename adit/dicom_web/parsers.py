import io
import logging
from collections.abc import AsyncIterator

from django.http import HttpRequest
from pydicom import Dataset
from pydicom.errors import InvalidDicomError
from rest_framework.exceptions import NotAcceptable

from adit.core.utils.dicom_utils import read_dataset

logger = logging.getLogger(__name__)


async def parse_request_in_chunks(
    request: HttpRequest, chunk_size: int = 8192
) -> AsyncIterator[Dataset]:
    try:
        media_type: str | None = request.content_type
        assert media_type is not None, "Content-Type header is required"
        boundary: bytes = b"--" + media_type.split("boundary=")[1].strip('"').encode()
    except (IndexError, AssertionError):
        raise NotAcceptable("Invalid multipart request with no boundary")

    buffer: bytes = b""
    while True:
        chunk: bytes = request.read(chunk_size)

        if not chunk:
            # Flush any part still buffered at the end of the stream.
            if buffer:
                ds = await _get_dicom_from_part(buffer)
                if ds is not None:
                    yield ds
            break

        buffer += chunk

        # A single read may contain several boundaries (multiple small parts),
        # so split out every complete part, not just the first one. Any partial
        # trailing part (or a boundary split across reads) stays in the buffer.
        idx = buffer.find(boundary)
        while idx != -1:
            part = buffer[:idx]
            if part:
                ds = await _get_dicom_from_part(part)
                if ds is not None:
                    yield ds
            buffer = buffer[idx + len(boundary) :]
            idx = buffer.find(boundary)


async def _get_dicom_from_part(part: bytes) -> Dataset | None:
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
            return read_dataset(io.BytesIO(content))
        except InvalidDicomError:
            logger.error("Invalid DICOM data in multipart request.")
            return None

    return None
