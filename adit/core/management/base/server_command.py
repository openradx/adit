import errno
import os
import signal
import sys
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import autoreload as django_autoreload


class ServerCommand(BaseCommand):
    """See Django's runserver.py command.

    https://github.com/django/django/blob/master/django/core/management/commands/runserver.py
    """

    help = "Starts a custom server"
    autoreload = False
    server_name = "custom server"

    def add_arguments(self, parser):
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Autoreload server on code change.",
        )

    def handle(self, *args, **options):
        self.run(**options)

    def run(self, **options):
        try:
            # Listens for the SIGTERM signal from stopping the Docker container. Only
            # with this listener the finally block is executed as sys.exit(0) throws
            # an exception.
            signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))

            if options["autoreload"] or self.autoreload:
                django_autoreload.run_with_reloader(self.inner_run, **options)
            else:
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
        finally:
            self.on_shutdown()

    def inner_run(self, **options):
        # If an exception was silenced in ManagementUtility.execute in order
        # to be raised in the child process, raise it now.
        django_autoreload.raise_last_exception()

        self.stdout.write("Performing system checks...\n\n")
        self.check(display_num_errors=True)

        now = datetime.now().strftime("%B %d, %Y - %X")
        self.stdout.write(now)
        self.stdout.write(f"Starting {self.server_name}")
        self.stdout.write("Quit with CONTROL-C.")

        self.run_server(**options)

    def run_server(self, **options):
        raise NotImplementedError()

    def on_shutdown(self):
        pass
