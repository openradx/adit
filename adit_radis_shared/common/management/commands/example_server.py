import time

from adit_radis_shared.common.management.base.server_command import ServerCommand


class Command(ServerCommand):
    help = "Just an async example server"
    server_name = "Example async server"

    stop = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run_server(self, **options):
        while not self.stop:
            self.stdout.write(".", ending="")
            self.stdout.flush()
            time.sleep(1)

    def on_shutdown(self):
        self.stop = True
