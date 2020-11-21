import logging
import time
import json
from io import BytesIO
import pika
from pymongo import MongoClient
import gridfs
from django.core.management.base import BaseCommand
from django.conf import settings
from pynetdicom import AE, evt, AllStoragePresentationContexts, debug_logger
from pydicom.filebase import DicomFileLike
from pydicom.filewriter import dcmwrite

logger = logging.getLogger(__name__)

# debug_logger()


# def write_dataset_to_bytes(dataset):
#     # create a buffer
#     with BytesIO() as buffer:
#         # create a DicomFileLike object that has some properties of DataSet
#         memory_dataset = DicomFileLike(buffer)
#         # write the dataset to the DicomFileLike object
#         dcmwrite(memory_dataset, dataset)
#         # to read from the object, you have to rewind it
#         memory_dataset.seek(0)
#         # read the contents as bytes
#         return memory_dataset


# Implement a handler for evt.EVT_C_STORE
def handle_store(event):
    """Handle a C-STORE request event."""

    start = time.time()

    # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
    ds = event.dataset

    # Get calling AE Title: event.assoc.remote["ae_title"]
    # Get called AE Title event.assoc.acceptor.primitive.called_ae_title

    # Add the File Meta Information
    ds.file_meta = event.file_meta

    buffer = BytesIO()
    dcmwrite(buffer, ds)

    # Save dataset to MongoDB GridFS
    db = MongoClient(settings.MONGO_URL).received_dicoms
    fs = gridfs.GridFS(db)

    file_id = fs.put(
        buffer,
        filename=ds.SOPInstanceUID,
        meta={
            "StudyInstanceUID": ds.StudyInstanceUID,
            "SeriesInstanceUID": ds.SeriesInstanceUID,
            "SOPInstanceUID": ds.SOPInstanceUID,
        },
    )

    print("####################")
    print(file_id)

    connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
    channel = connection.channel()
    channel.exchange_declare(exchange="received", exchange_type="direct")
    # Send the dataset to the worker
    source_ae = event.assoc.remote["ae_title"]
    key = f"{source_ae}\\{ds.StudyInstanceUID}"
    channel.basic_publish(
        exchange="received_dicoms", routing_key=key, body=str(file_id)
    )

    connection.close()

    end = time.time()

    print(end - start)

    # Return a 'Success' status
    return 0x0000


class Command(BaseCommand):
    help = "Starts a C-STORE SCP for receiving DICOM files."

    def handle(self, *args, **options):
        handlers = [(evt.EVT_C_STORE, handle_store)]

        # Initialise the Application Entity
        ae = AE()

        # Support presentation contexts for all storage SOP Classes
        ae.supported_contexts = AllStoragePresentationContexts

        logger.info("Starting ADIT DICOM Receiver.")

        # Start listening for incoming association requests
        ae.start_server(("", 11112), evt_handlers=handlers)
