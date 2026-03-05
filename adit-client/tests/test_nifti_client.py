from unittest.mock import MagicMock, patch

import pytest
from adit_client.client import AditClient


class TestExtractFilename:
    def test_valid_filename(self):
        client = AditClient("http://localhost", "token")
        result = client._extract_filename('attachment; filename="scan.nii.gz"')
        assert result == "scan.nii.gz"

    def test_filename_with_path(self):
        client = AditClient("http://localhost", "token")
        result = client._extract_filename('attachment; filename="path/to/scan.nii.gz"')
        assert result == "scan.nii.gz"

    def test_missing_header(self):
        client = AditClient("http://localhost", "token")
        with pytest.raises(ValueError, match="No filename found"):
            client._extract_filename(None)

    def test_no_filename_field(self):
        client = AditClient("http://localhost", "token")
        with pytest.raises(ValueError, match="No filename found"):
            client._extract_filename("attachment")


class TestExtractPartContentWithHeaders:
    def test_empty_bytes(self):
        client = AditClient("http://localhost", "token")
        assert client._extract_part_content_with_headers(b"") is None

    def test_boundary_marker(self):
        client = AditClient("http://localhost", "token")
        assert client._extract_part_content_with_headers(b"--") is None

    def test_crlf(self):
        client = AditClient("http://localhost", "token")
        assert client._extract_part_content_with_headers(b"\r\n") is None

    def test_boundary_with_crlf(self):
        client = AditClient("http://localhost", "token")
        assert client._extract_part_content_with_headers(b"--\r\n") is None

    def test_normal_content(self):
        client = AditClient("http://localhost", "token")
        part = b"Content-Type: application/octet-stream\r\n\r\ndata"
        assert client._extract_part_content_with_headers(part) == part


class TestIterMultipartResponse:
    def test_parses_parts_with_content_disposition(self):
        client = AditClient("http://localhost", "token")

        # Create a fake part with headers + content separated by \r\n\r\n
        part = (
            b"Content-Type: application/octet-stream\r\n"
            b'Content-Disposition: attachment; filename="scan.nii.gz"\r\n'
            b"\r\n"
            b"nifti content"
        )

        fake_dicomweb_client = MagicMock()
        fake_dicomweb_client._decode_multipart_message.return_value = [part]
        # Let _extract_part_content return part as-is (our patched method)
        fake_dicomweb_client._extract_part_content = client._extract_part_content_with_headers

        response = MagicMock()
        response.headers = {}

        with patch.object(client, "_create_dicom_web_client", return_value=fake_dicomweb_client):
            results = list(client._iter_multipart_response(response, stream=False))

        assert len(results) == 1
        assert results[0][0] == "scan.nii.gz"
        assert results[0][1].read() == b"nifti content"

    def test_falls_back_to_response_headers(self):
        client = AditClient("http://localhost", "token")

        # Part without Content-Disposition (no \r\n\r\n separator means no headers parsed)
        part = b"just raw content without headers"

        fake_dicomweb_client = MagicMock()
        fake_dicomweb_client._decode_multipart_message.return_value = [part]
        fake_dicomweb_client._extract_part_content = client._extract_part_content_with_headers

        fake_headers = MagicMock()
        fake_headers.items.return_value = [
            ("content-disposition", 'attachment; filename="fallback.nii.gz"')
        ]
        fake_headers.get.return_value = None

        response = MagicMock()
        response.headers = fake_headers

        with patch.object(client, "_create_dicom_web_client", return_value=fake_dicomweb_client):
            results = list(client._iter_multipart_response(response, stream=False))

        assert len(results) == 1
        assert results[0][0] == "fallback.nii.gz"

    def test_no_disposition_anywhere_raises(self):
        client = AditClient("http://localhost", "token")

        part = b"content without any disposition"

        fake_dicomweb_client = MagicMock()
        fake_dicomweb_client._decode_multipart_message.return_value = [part]
        fake_dicomweb_client._extract_part_content = client._extract_part_content_with_headers

        fake_headers = MagicMock()
        fake_headers.items.return_value = []
        fake_headers.get.return_value = None

        response = MagicMock()
        response.headers = fake_headers

        with patch.object(client, "_create_dicom_web_client", return_value=fake_dicomweb_client):
            with pytest.raises(ValueError, match="No Content-Disposition"):
                list(client._iter_multipart_response(response, stream=False))
