import asyncio
from os import DirEntry
from typing import Callable

from aiofiles import os
from asyncinotify import Inotify, Mask

FileHandler = Callable[[str], bool | None]
ScanHandler = Callable[[], None]


class FileMonitor:
    def __init__(self, folder: str):
        self._root_folder = folder
        self._queue = asyncio.Queue(maxsize=2)
        self._task_group: asyncio.Future | None = None

    async def _scan_path(self, path: str, file_handler: FileHandler):
        if await os.path.isfile(path):
            is_processed = False
            if asyncio.iscoroutinefunction(file_handler):
                is_processed = await file_handler(path)
            else:
                is_processed = file_handler(path)

            if is_processed:
                await os.unlink(path)

        elif await os.path.isdir(path):
            entries: list[DirEntry] = await os.scandir(path)
            for entry in entries:
                await self._scan_path(entry.path, file_handler)

            # Clean up empty directories
            is_empty = not any(await os.scandir(path))
            if path != self._root_folder and is_empty:
                try:
                    await os.rmdir(path)
                except OSError:
                    # It could be that just in this moment a file is written to
                    # the directory and then a OSError is raised because it is
                    # not empty anymore
                    pass

    async def _worker(self, file_handler: FileHandler, scan_handler: ScanHandler | None):
        while True:
            await self._queue.get()
            await self._scan_path(self._root_folder, file_handler)
            self._queue.task_done()

            if scan_handler:
                if asyncio.iscoroutinefunction(scan_handler):
                    await scan_handler()
                else:
                    scan_handler()

    async def _schedule_scan(self):
        try:
            self._queue.put_nowait(True)
        except asyncio.QueueFull:
            # If there is already one further scan job in the queue we don't have
            # to add another one.
            pass

    async def _watch_folder(self):
        with Inotify() as inotify:
            inotify.add_watch(self._root_folder, Mask.CREATE | Mask.DELETE | Mask.MODIFY)
            async for event in inotify:
                await self._schedule_scan()

    async def _periodic_scan(self):
        while True:
            await asyncio.sleep(60)
            await self._schedule_scan()

    async def start(self, file_handler: FileHandler, scan_handler: ScanHandler | None = None):
        exists = await os.path.exists(self._root_folder)
        is_dir = await os.path.isdir(self._root_folder)
        if not exists or not is_dir:
            raise IOError(f"Invalid directory to monitor: {self._root_folder}")

        worker_task = asyncio.create_task(self._worker(file_handler, scan_handler))

        watch_folder_task = asyncio.create_task(self._watch_folder())

        periodic_scan_task = asyncio.create_task(self._periodic_scan())

        # Force one initial scan when the file monitor starts
        await self._schedule_scan()

        self._task_group = asyncio.gather(worker_task, watch_folder_task, periodic_scan_task)
        await self._task_group

    async def stop(self):
        if self._task_group:
            self._task_group.cancel()
