import logging
from io import BytesIO
from functools import partial
import signal
import time
import sys
import pika
from pika.exceptions import AMQPConnectionError
from django.utils import autoreload
from django.core.management.base import BaseCommand
from django.conf import settings
from pynetdicom import AE, evt, AllStoragePresentationContexts, debug_logger
from pydicom.filewriter import dcmwrite

FORCE_DEBUG_LOGGER = False

logger = logging.getLogger(__name__)

# Implement a handler for evt.EVT_C_STORE
def handle_store(connection, event):
    """Handle a C-STORE request event.

    The request is initiated with a C-MOVE request by ADIT itself to
    fetch images from a DICOM server that doesn't support C-GET requests.
    """
    ds = event.dataset
    ds.file_meta = event.file_meta

    called_ae = event.assoc.acceptor.primitive.called_ae_title
    called_ae = called_ae.decode("utf-8").strip()
    if called_ae != settings.ADIT_AE_TITLE:
        raise AssertionError(f"Invalid called AE title: {called_ae}")

    buffer = BytesIO()
    dcmwrite(buffer, ds, write_like_original=False)

    channel = connection.channel()
    channel.exchange_declare(exchange="received", exchange_type="direct")

    # Send the dataset to the workers using RabbitMQ
    calling_ae = event.assoc.remote["ae_title"].decode("utf-8").strip()
    routing_key = f"{calling_ae}\\{ds.StudyInstanceUID}\\{ds.SeriesInstanceUID}"
    properties = pika.BasicProperties(message_id=ds.SOPInstanceUID)
    channel.basic_publish(
        exchange="received_dicoms",
        routing_key=routing_key,
        properties=properties,
        body=buffer.getvalue(),
    )

    buffer.close()
    channel.close()

    return 0x0000  # Return a 'Success' status


def run_store_scp_server(connection):
    ae = AE(ae_title=settings.ADIT_AE_TITLE)
    ae.supported_contexts = AllStoragePresentationContexts
    handlers = [(evt.EVT_C_STORE, partial(handle_store, connection))]
    logger.info("Starting ADIT DICOM C-STORE SCP Receiver.")
    ae.start_server(("", 11112), evt_handlers=handlers)


class Command(BaseCommand):
    help = "Starts a C-STORE SCP for receiving DICOM files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--autoreload",
            action="store_true",
            help="Auto reload C-STORE SCP server on code change.",
        )
        parser.add_argument(
            "--debug-logger",
            action="store_true",
            help="Enable debug logger of pynetdicom.",
        )

    def handle(self, *args, **options):
        rabbit_url = settings.RABBITMQ_URL
        connection = None
        for i in range(100):
            try:
                connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
                break
            except AMQPConnectionError:
                logger.error(
                    "Cannot connect to %s. Trying again in 2 seconds... (%d/100).",
                    rabbit_url,
                    i + 1,
                )
            time.sleep(2)

        if connection and connection.is_open:
            logger.info("Connected to %s.", rabbit_url)
        else:
            logger.error("Could not connect to %s. No more retries", rabbit_url)
            sys.exit(1)

        if options["debug-logger"] or FORCE_DEBUG_LOGGER:
            debug_logger()

        try:
            # Listens for the SIGTERM signal from stopping the Docker container. Only
            # with this listener the finally block is executed as sys.exit(0) throws
            # an exception.
            signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
            if options["autoreload"]:
                autoreload.run_with_reloader(partial(run_store_scp_server, connection))
            else:
                run_store_scp_server(connection)
        finally:
            connection.close()
