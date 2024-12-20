from django.conf import settings
from django.core.management.base import BaseCommand

from adit.core.utils.orthanc_utils import OrthancRestHandler


class Command(BaseCommand):
    help = "Clear both Orthanc instances and upload DICOM files to Orthanc 1 instance."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        orthanc1 = OrthancRestHandler(host=settings.ORTHANC1_HOST, port=settings.ORTHANC1_HTTP_PORT)
        orthanc2 = OrthancRestHandler(host=settings.ORTHANC2_HOST, port=settings.ORTHANC2_HTTP_PORT)

        if options["reset"]:
            self.stdout.write("Resetting Orthancs...", ending="")
            self.stdout.flush()
            orthanc1.clear()
            orthanc2.clear()
            self.stdout.write("Done")

        if len(orthanc1.list()) > 0:
            self.stdout.write("Orthanc1 already populated with DICOM data. Skipping.")
            return

        self.stdout.write("Populating Orthanc1 with example DICOMs...", ending="")
        self.stdout.flush()
        dicoms_folder = settings.BASE_DIR / "samples" / "dicoms"
        orthanc1.upload(dicoms_folder)
        self.stdout.write("Done")
