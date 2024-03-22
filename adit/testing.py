from functools import partial

from channels.routing import get_default_application
from daphne.testing import DaphneProcess
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # type: ignore
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.utils import modify_settings


def _make_application(*, static_wrapper):
    # Module-level function for pickle-ability
    application = get_default_application()
    if static_wrapper is not None:
        application = static_wrapper(application)
    return application


class ChannelsLiveServer:
    host = "localhost"
    ProtocolServerProcess = DaphneProcess
    static_wrapper = ASGIStaticFilesHandler
    serve_static = True

    def __init__(self) -> None:
        for connection in connections.all():
            if connection.vendor == "sqlite" and connection.is_in_memory_db():
                raise ImproperlyConfigured(
                    "ChannelsLiveServer can not be used with in memory databases"
                )

        self._live_server_modified_settings = modify_settings(ALLOWED_HOSTS={"append": self.host})
        self._live_server_modified_settings.enable()

        get_application = partial(
            _make_application,
            static_wrapper=self.static_wrapper if self.serve_static else None,
        )

        self._server_process = self.ProtocolServerProcess(self.host, get_application)
        self._server_process.start()
        self._server_process.ready.wait()
        self._port = self._server_process.port.value

    def stop(self) -> None:
        self._server_process.terminate()
        self._server_process.join()
        self._live_server_modified_settings.disable()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self._port}"
