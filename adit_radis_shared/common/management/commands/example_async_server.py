import asyncio

from adit_radis_shared.common.management.base.server_command import AsyncServerCommand


class Command(AsyncServerCommand):
    help = "Just an example server"
    server_name = "Example server"

    stop = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run_server_async(self, **options):
        while not self.stop:
            self.stdout.write(".", ending="")
            self.stdout.flush()
            await asyncio.sleep(1)

    def on_shutdown(self):
        self.stop = True
