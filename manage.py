#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adit.settings.development")

    # Initialize OpenTelemetry before Django loads to ensure all requests are traced
    from adit.telemetry import setup_opentelemetry

    setup_opentelemetry()

    initialize_debugger()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


def initialize_debugger():
    """Enable remote debugging."""
    from django.conf import settings

    # RUN_MAIN envvar is set by the reloader to indicate that this is the
    # actual thread running Django.
    if settings.DEBUG and settings.REMOTE_DEBUGGING_ENABLED and os.getenv("RUN_MAIN"):
        import debugpy

        debugpy.listen(("0.0.0.0", settings.REMOTE_DEBUGGING_PORT))
        sys.stdout.write("Start the VS Code debugger now, waiting...\n")
        debugpy.wait_for_client()
        sys.stdout.write("Debugger attached, starting server...\n")


if __name__ == "__main__":
    main()
