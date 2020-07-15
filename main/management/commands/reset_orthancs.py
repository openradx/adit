from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
from main.tests.helpers.orthanc_rest_handler import OrthancRestHandler

class Command(BaseCommand):
    help = 'Clear both Orthanc instances and upload DICOM files to Orthanc 1 instance.'

    def handle(self, *args, **options):
        
        dicoms_folder = Path(settings.BASE_DIR) / '_debug' / 'samples' / 'dicoms'
        handler = OrthancRestHandler(port=6501)
        handler.clear()
        handler.upload_files(dicoms_folder)

        handler = OrthancRestHandler(port=6502)
        handler.clear()
