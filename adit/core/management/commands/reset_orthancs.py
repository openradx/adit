from os import environ
from django.conf import settings
from django.core.management.base import BaseCommand
from adit.core.utils.orthanc_utils import OrthancRestHandler


class Command(BaseCommand):
    help = "Clear both Orthanc instances and upload DICOM files to Orthanc 1 instance."

    def handle(self, *args, **options):
        print("Resetting Orthancs.")

        dicoms_folder = settings.BASE_DIR / "samples" / "dicoms"

        orthanc1_host = environ.get("ORTHANC1_HOST", "localhost")
        handler = OrthancRestHandler(host=orthanc1_host, port=6501)
        handler.clear()

        handler.upload(dicoms_folder)

        orthanc2_host = environ.get("ORTHANC2_HOST", "localhost")
        handler = OrthancRestHandler(host=orthanc2_host, port=6502)
        handler.clear()
