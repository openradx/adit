import asyncio
import signal
import subprocess
import sys
from abc import ABC, abstractmethod
from datetime import datetime

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

    def add_arguments(self, parser):
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Autoreload server on code change.",
        )

    def handle(self, *args, **options):
        # SIGINT is sent by CTRL-C
        signal.signal(signal.SIGINT, lambda signum, frame: self.terminate())
        # SIGTERM is sent when stopping a Docker container
        signal.signal(signal.SIGTERM, lambda signum, frame: self.terminate())

        self.run(**options)

    def run(self, **options):
        try:
            if options["autoreload"]:
                self.stdout.write(f"Autoreload enabled for {self.server_name}.")

                def inner_run():
                    if self._popen:
                        self._popen.terminate()

                    args = sys.argv.copy()
                    args.remove("--autoreload")
                    self._popen = subprocess.Popen(args, close_fds=False)

                inner_run()

                for changes in watch(settings.BASE_DIR / "adit", watch_filter=PythonFilter()):
                    self.stdout.write("Changes detected. Restarting server...")
                    inner_run()
            else:
                self.stdout.write("Performing system checks...")
                self.check(display_num_errors=True)

                self.stdout.write(datetime.now().strftime("%B %d, %Y - %X"))
                self.stdout.write(f"Starting {self.server_name}")
                self.stdout.write("Quit with CONTROL-C.")

                self.run_server(**options)

        except KeyboardInterrupt:
            sys.exit(0)

    def terminate(self):
        if self._popen:
            self._popen.terminate()

        self.on_shutdown()

    @abstractmethod
    def run_server(self, **options):
        raise NotImplementedError

    @abstractmethod
    def on_shutdown(self):
        raise NotImplementedError


class AsyncServerCommand(ServerCommand, ABC):
    def handle(self, *args, **options):
        self.run(**options)

    def run_server(self, **options):
        loop = asyncio.get_event_loop()

        # SIGINT is sent by CTRL-C
        loop.add_signal_handler(signal.SIGINT, lambda: self.terminate())
        # SIGTERM is sent when stopping a Docker container
        loop.add_signal_handler(signal.SIGTERM, lambda: self.terminate())

        try:
            loop.run_until_complete(self.run_server_async())
        except asyncio.CancelledError:
            sys.exit(0)

    @abstractmethod
    async def run_server_async(self, **options):
        raise NotImplementedError
