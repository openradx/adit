from io import BytesIO

import pytest

from adit.dicom_web.renderers import WadoMultipartApplicationNiftiRenderer


async def _collect_rendered_output(renderer, images):
    chunks = []
    async for chunk in renderer.render(images):
        chunks.append(chunk)
    return b"".join(chunks)


async def _async_iter(items):
    for item in items:
        yield item


class TestWadoMultipartApplicationNiftiRenderer:
    @pytest.mark.asyncio
    async def test_render_single_file(self):
        renderer = WadoMultipartApplicationNiftiRenderer()
        content = b"fake nifti data"
        files = [("scan.nii.gz", BytesIO(content))]

        output = await _collect_rendered_output(renderer, _async_iter(files))

        assert b"--nifti-boundary\r\n" in output
        assert b"Content-Type: application/octet-stream\r\n" in output
        assert b'Content-Disposition: attachment; filename="scan.nii.gz"' in output
        assert content in output
        assert output.endswith(b"\r\n--nifti-boundary--\r\n")

    @pytest.mark.asyncio
    async def test_render_multiple_files(self):
        renderer = WadoMultipartApplicationNiftiRenderer()
        files = [
            ("scan.json", BytesIO(b'{"key": "value"}')),
            ("scan.nii.gz", BytesIO(b"nifti data")),
        ]

        output = await _collect_rendered_output(renderer, _async_iter(files))

        # First file starts without leading \r\n
        assert output.startswith(b"--nifti-boundary\r\n")
        # Second file separated by \r\n--boundary\r\n
        assert b"\r\n--nifti-boundary\r\n" in output
        # Both filenames present
        assert b'filename="scan.json"' in output
        assert b'filename="scan.nii.gz"' in output
        assert output.endswith(b"\r\n--nifti-boundary--\r\n")

    @pytest.mark.asyncio
    async def test_render_empty_iterator(self):
        renderer = WadoMultipartApplicationNiftiRenderer()

        output = await _collect_rendered_output(renderer, _async_iter([]))

        # Only the closing boundary
        assert output == b"\r\n--nifti-boundary--\r\n"

    @pytest.mark.asyncio
    async def test_render_filename_sanitization(self):
        renderer = WadoMultipartApplicationNiftiRenderer()
        malicious_name = 'bad\r\nname"file.nii.gz'
        files = [(malicious_name, BytesIO(b"data"))]

        output = await _collect_rendered_output(renderer, _async_iter(files))

        # \r, \n, and " should be stripped
        assert b'filename="badnamefile.nii.gz"' in output
        assert b"\r\nname" not in output.split(b"Content-Disposition")[1].split(b"\r\n\r\n")[0]

    def test_content_type_property(self):
        renderer = WadoMultipartApplicationNiftiRenderer()

        assert renderer.content_type == (
            "multipart/related; type=application/octet-stream; boundary=nifti-boundary"
        )
