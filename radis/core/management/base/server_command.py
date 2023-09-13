import asyncio
import signal
import subprocess
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from threading import Event

from django.conf import settings
from django.core.management.base import BaseCommand
from watchfiles import PythonFilter, watch


class ServerCommand(BaseCommand, ABC):
    """See Django's runserver.py command.

    https://github.com/django/django/blob/master/django/core/management/commands/runserver.py
    """

    help = "Starts a custom server"
    server_name = "custom server"

    _popen: subprocess.Popen | None = None
    _stop = Event()

    def add_arguments(self, parser):
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Autoreload server on code change.",
        )

    def handle(self, *args, **options):
        # SIGINT is sent by CTRL-C
        signal.signal(
            signal.SIGINT, lambda signum, frame: (self._on_terminate(), self.on_shutdown())
        )
        # SIGTERM is sent when stopping a Docker container
        signal.signal(
            signal.SIGTERM, lambda signum, frame: (self._on_terminate(), self.on_shutdown())
        )

        self.run(**options)

    def run(self, **options):
        if options["autoreload"]:
            self.stdout.write(f"Autoreload enabled for {self.server_name}.")

            def inner_run():
                if self._popen:
                    self._popen.terminate()

                args = sys.argv.copy()
                args.remove("--autoreload")
                self._popen = subprocess.Popen(args, close_fds=False)

            inner_run()

            try:
                for changes in watch(
                    settings.BASE_DIR / "radis", watch_filter=PythonFilter(), stop_event=self._stop
                ):
                    self.stdout.write("Changes detected. Restarting server...")
                    inner_run()
            except KeyboardInterrupt:
                # watch itself tries to catch signals and may raise a KeyboardInterrupt, but we
                # handle all signals ourselves
                pass

            if self._popen:
                self._popen.wait()
        else:
            self.stdout.write("Performing system checks...")
            self.check(display_num_errors=True)

            self.stdout.write(datetime.now().strftime("%B %d, %Y - %X"))
            self.stdout.write(f"Starting {self.server_name}")
            self.stdout.write("Quit with CONTROL-C.")

            self.run_server(**options)

    def _on_terminate(self):
        if self._popen:
            self._popen.terminate()

        self._stop.set()

    @abstractmethod
    def run_server(self, **options):
        raise NotImplementedError

    @abstractmethod
    def on_shutdown(self):
        raise NotImplementedError


class AsyncServerCommand(ServerCommand, ABC):
    def handle(self, *args, **options):
        # SIGINT is sent by CTRL-C
        signal.signal(signal.SIGINT, lambda signum, frame: self._on_terminate())
        # SIGTERM is sent when stopping a Docker container
        signal.signal(signal.SIGTERM, lambda signum, frame: self._on_terminate())

        self.run(**options)

    def run_server(self, **options):
        loop = asyncio.get_event_loop()

        # Shutdown in asyncio loop must be handled by a different signal handler
        loop.add_signal_handler(signal.SIGINT, lambda: self.on_shutdown())
        loop.add_signal_handler(signal.SIGTERM, lambda: self.on_shutdown())

        loop.run_until_complete(self.run_server_async())

    @abstractmethod
    async def run_server_async(self, **options):
        raise NotImplementedError