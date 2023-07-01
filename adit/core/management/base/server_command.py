import errno
import os
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
        self.run(**options)

    def run(self, **options):
        def handle_shutdown(*args):
            self.on_shutdown()
            raise KeyboardInterrupt()

        # SIGINT is sent by CTRL-C
        signal.signal(signal.SIGINT, handle_shutdown)
        # SIGTERM is sent when stopping a Docker container
        signal.signal(signal.SIGTERM, handle_shutdown)

        try:
            self.inner_run(**options)
        except OSError as e:
            # Use helpful error messages instead of ugly tracebacks.
            ERRORS = {
                errno.EACCES: "You don't have permission to access that port.",
                errno.EADDRINUSE: "That port is already in use.",
                errno.EADDRNOTAVAIL: "That IP address can't be assigned to.",
            }
            try:
                error_text = ERRORS[e.errno]
            except KeyError:
                error_text = e
            self.stderr.write(f"Error: {error_text}")
            # Need to use an OS exit because sys.exit doesn't work in a thread
            os._exit(1)
        except KeyboardInterrupt:
            sys.exit(0)

    def inner_run(self, **options):
        self.stdout.write("Performing system checks...\n\n")
        self.check(display_num_errors=True)

        now = datetime.now().strftime("%B %d, %Y - %X")
        self.stdout.write(now)
        self.stdout.write(f"Starting {self.server_name}")
        self.stdout.write("Quit with CONTROL-C.")

        self.run_server(**options)

    def run_server(self, **options):
        raise NotImplementedError()

    @abstractmethod
    def on_shutdown(self):
        pass
