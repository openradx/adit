import errno
import os
import re
import signal
import socket
import sys
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import autoreload as django_autoreload
from django.utils.regex_helper import _lazy_re_compile

naiveip_re = _lazy_re_compile(
    r"""^(?:
(?P<addr>
    (?P<ipv4>\d{1,3}(?:\.\d{1,3}){3}) |         # IPv4 address
    (?P<ipv6>\[[a-fA-F0-9:]+\]) |               # IPv6 address
    (?P<fqdn>[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*) # FQDN
):)?(?P<port>\d+)$""",
    re.X,
)


class ServerCommand(BaseCommand):
    """Heavily inspired by Django's runserver.py command.

    https://github.com/django/django/blob/master/django/core/management/commands/runserver.py
    """

    # Validation is called explicitly each time the server is reloaded.
    requires_system_checks = "__all__"

    autoreload = False
    starting_message = True
    server_name = "custom server"
    default_addr = "127.0.0.1"
    default_addr_ipv6 = "::1"
    default_port = 80
    protocol = "http"

    def __init__(self, *args, **kwargs):
        self.addr = None
        self.port = None
        self.use_ipv6 = None
        self._raw_ipv6 = None
        self.quit_command = "CTRL-BREAK" if sys.platform == "win32" else "CONTROL-C"
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("addrport", nargs="?", help="Optional port number, or ipaddr:port")
        parser.add_argument(
            "--ipv6",
            "-6",
            action="store_true",
            dest="use_ipv6",
            help="Tells the server to use an IPv6 address.",
        )
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Autoreload server on code change.",
        )

    def handle(self, *args, **options):
        self.use_ipv6 = options["use_ipv6"]

        if self.use_ipv6 and not socket.has_ipv6:
            raise CommandError("Your Python does not support IPv6.")
        self._raw_ipv6 = False
        if not options["addrport"]:
            self.addr = ""
            self.port = self.default_port
        else:
            m = re.match(naiveip_re, options["addrport"])
            if m is None:
                raise CommandError(f'"{options["addrport"]}" is not a valid port number ' "or address:port pair.")
            self.addr, _ipv4, _ipv6, _fqdn, self.port = m.groups()
            if not self.port.isdigit():
                raise CommandError(f"{self.port} is not a valid port number.")
            if self.addr:
                if _ipv6:
                    self.addr = self.addr[1:-1]
                    self.use_ipv6 = True
                    self._raw_ipv6 = True
                elif self.use_ipv6 and not _fqdn:
                    raise CommandError(f'"{self.addr}" is not a valid IPv6 address.')
        if not self.addr:
            self.addr = self.default_addr_ipv6 if self.use_ipv6 else self.default_addr
            self._raw_ipv6 = self.use_ipv6

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

        if self.starting_message:
            now = datetime.now().strftime("%B %d, %Y - %X")
            self.stdout.write(now)
            self.stdout.write(
                ("Starting %(name)s at %(protocol)s://%(addr)s:%(port)s/\n" "Quit with %(quit_command)s.")
                % {
                    "name": self.server_name,
                    "protocol": self.protocol,
                    "addr": f"[{self.addr if self._raw_ipv6 else self.addr}]",
                    "port": self.port,
                    "quit_command": self.quit_command,
                }
            )

        self.run_server(**options)

    def run_server(self, **options):
        raise NotImplementedError()

    def on_shutdown(self):
        pass
