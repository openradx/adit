import logging
import time
from django.core.management.base import BaseCommand
from pynetdicom import AE, evt, AllStoragePresentationContexts, debug_logger

logger = logging.getLogger(__name__)

# debug_logger()

# Implement a handler for evt.EVT_C_STORE
def handle_store(event):
    """Handle a C-STORE request event."""
    # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
    ds = event.dataset

    # Get calling AE Title: event.assoc.remote["ae_title"]
    # Get called AE Title event.assoc.acceptor.primitive.called_ae_title

    # Add the File Meta Information
    ds.file_meta = event.file_meta

    # Save the dataset using the SOP Instance UID as the filename
    # ds.save_as(ds.SOPInstanceUID, write_like_original=False)

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
