import asyncio
import os
from tempfile import TemporaryDirectory

import pytest

from adit.core.utils.file_monitor import FileMonitor


def is_folder_empty(folder: str):
    return next(os.scandir(folder), None) is None


@pytest.mark.asyncio
async def test_file_monitor_detects_file_and_removes_it(create_dummy_file):
    with TemporaryDirectory() as temp_dir:
        dummy_size = 10240  # 10kb
        create_dummy_file(temp_dir, ".dcm", dummy_size)

        monitor = FileMonitor(temp_dir)

        async def handle_file(filepath: str):
            assert os.path.getsize(filepath) == dummy_size
            await monitor.stop()
            return True

        monitor.set_file_handler(handle_file)

        try:
            await monitor.start()
        except asyncio.CancelledError:
            assert is_folder_empty(temp_dir)


@pytest.mark.asyncio
async def test_file_monitor_deletes_empty_subfolders():
    with TemporaryDirectory() as temp_dir:
        with TemporaryDirectory(dir=temp_dir):
            assert is_folder_empty(temp_dir) is False
            monitor = FileMonitor(temp_dir)

            async def handle_scan():
                await monitor.stop()

            monitor.set_after_scan_handler(handle_scan)

            try:
                await monitor.start()
            except asyncio.CancelledError:
                assert is_folder_empty(temp_dir) is True
