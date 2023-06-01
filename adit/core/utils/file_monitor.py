import asyncio
import logging
from os import DirEntry, PathLike
from typing import Awaitable, Callable

from aiofiles import os
from asyncinotify import Inotify, Mask

FileHandler = Callable[[PathLike], bool | None | Awaitable[bool] | Awaitable[None]]
BeforeScanHandler = Callable[[], None | Awaitable[None]]
AfterScanHandler = Callable[[], None | Awaitable[None]]

logger = logging.getLogger(__name__)


class FileMonitor:
    """Monitors a folder for new files and processes them."""

    def __init__(self, folder: PathLike):
        self._folder = folder

        # We use a queue to make sure that only one scan is running at a time.
        # A max size of 2 is enough as we only have to make sure that a succeeding
        # scan is started after the current one is finished (when a new file was
        # added to the folder during the running scan)
        self._queue = asyncio.Queue(maxsize=2)
        self._file_handler: FileHandler | None = None
        self._before_scan_handler: BeforeScanHandler | None = None
        self._after_scan_handler: AfterScanHandler | None = None
        self._scan_counter = 0
        self._task_group: asyncio.Future | None = None

    def set_file_handler(self, file_handler: FileHandler):
        """Sets the file handler that is called for each new file.

        It should return True if the file was processed successfully and False.
        If it returns True the file will be deleted afterwards.
        """
        self._file_handler = file_handler

    def set_before_scan_handler(self, before_scan_handler: BeforeScanHandler):
        """A callback that is called before a scan is started."""
        self._before_scan_handler = before_scan_handler

    def set_after_scan_handler(self, after_scan_handler: AfterScanHandler):
        """A callback that is called after a scan is finished."""
        self._after_scan_handler = after_scan_handler

    @property
    def scan_count(self):
        """Returns the number of scans that were performed since start."""
        self._scan_counter

    async def _scan_path(self, path: PathLike):
        if await os.path.isfile(path):
            is_processed = False
            if self._file_handler:
                if asyncio.iscoroutinefunction(self._file_handler):
                    is_processed = await self._file_handler(path)
                else:
                    is_processed = self._file_handler(path)

            if is_processed:
                await os.unlink(path)  # type: ignore

        elif await os.path.isdir(path):
            entries: list[DirEntry] = await os.scandir(path)  # type: ignore
            for entry in entries:
                await self._scan_path(entry.path)

            # Clean up empty directories
            is_empty = not any(await os.scandir(path))
            if path != self._folder and is_empty:
                try:
                    await os.rmdir(path)
                except OSError:
                    # It could be that just in this moment a file is written to
                    # the directory and then a OSError is raised because it is
                    # not empty anymore
                    pass

    async def _worker(self):
        while True:
            if self._before_scan_handler:
                if asyncio.iscoroutinefunction(self._before_scan_handler):
                    await self._before_scan_handler()
                else:
                    self._before_scan_handler()

            await self._queue.get()
            await self._scan_path(self._folder)
            self._queue.task_done()

            self._scan_counter += 1

            if self._after_scan_handler:
                if asyncio.iscoroutinefunction(self._after_scan_handler):
                    await self._after_scan_handler()
                else:
                    self._after_scan_handler()

    async def _schedule_scan(self):
        try:
            self._queue.put_nowait(True)
        except asyncio.QueueFull:
            # If there is already one further scan job in the queue we don't have
            # to add another one.
            pass

    async def _watch_folder(self):
        with Inotify() as inotify:
            inotify.add_watch(self._folder, Mask.CREATE | Mask.DELETE | Mask.MODIFY)
            async for event in inotify:
                await self._schedule_scan()

    async def _periodic_scan(self):
        while True:
            # Force a re-scan every minute
            await asyncio.sleep(60)
            await self._schedule_scan()

    async def start(self):
        if not await os.path.exists(self._folder) or not await os.path.isdir(self._folder):
            raise IOError(f"Invalid directory to monitor: {self._folder}")

        self._scan_counter = 0

        logger.info(f"Start monitoring folder {self._folder}")

        worker_task = asyncio.create_task(self._worker())

        watch_folder_task = asyncio.create_task(self._watch_folder())

        periodic_scan_task = asyncio.create_task(self._periodic_scan())

        # Force one initial scan when the file monitor starts
        await self._schedule_scan()

        self._task_group = asyncio.gather(worker_task, watch_folder_task, periodic_scan_task)
        await self._task_group

    async def stop(self):
        if self._task_group:
            self._task_group.cancel()

        logger.info("File monitor stopped")
