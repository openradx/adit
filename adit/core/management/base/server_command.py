import asyncio
import signal
import sys
from abc import ABC, abstractmethod
from datetime import datetime

from django.core.management.base import BaseCommand


class ServerCommand(BaseCommand, ABC):
    """See Django's runserver.py command.

    https://github.com/django/django/blob/master/django/core/management/commands/runserver.py
    """

    help = "Starts a custom server"
    server_name = "custom server"

    def handle(self, *args, **options):
        # SIGINT is sent by CTRL-C
        signal.signal(signal.SIGINT, lambda signum, frame: self.on_shutdown())
        # SIGTERM is sent when stopping a Docker container
        signal.signal(signal.SIGTERM, lambda signum, frame: self.on_shutdown())

        self.run(**options)

    def run(self, **options):
        try:
            self.stdout.write("Performing system checks...\n\n")
            self.check(display_num_errors=True)

            now = datetime.now().strftime("%B %d, %Y - %X")
            self.stdout.write(now)
            self.stdout.write(f"Starting {self.server_name}")
            self.stdout.write("Quit with CONTROL-C.")

            self.run_server(**options)
        except KeyboardInterrupt:
            sys.exit(0)

    @abstractmethod
    def run_server(self, **options):
        raise NotImplementedError

    def on_shutdown(self):
        raise KeyboardInterrupt


class AsyncServerCommand(ServerCommand, ABC):
    def handle(self, *args, **options):
        self.run(**options)

    def run_server(self, **options):
        loop = asyncio.get_event_loop()

        # SIGINT is sent by CTRL-C
        loop.add_signal_handler(signal.SIGINT, lambda: self.on_shutdown())
        # SIGTERM is sent when stopping a Docker container
        loop.add_signal_handler(signal.SIGTERM, lambda: self.on_shutdown())

        try:
            loop.run_until_complete(self.run_server_async())
        except asyncio.CancelledError:
            sys.exit(0)

    @abstractmethod
    async def run_server_async(self, **options):
        raise NotImplementedError
