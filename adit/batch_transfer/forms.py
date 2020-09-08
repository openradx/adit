from io import StringIO
from django.forms import ModelForm
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import formats
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Div
import cchardet as chardet
from adit.main.models import DicomNode
from .models import BatchTransferJob, BatchTransferRequest
from .fields import RestrictedFileField
from .utils.request_parsers import RequestParser, ParsingError


class BatchTransferJobForm(ModelForm):
    csv_file = RestrictedFileField(max_upload_size=5242880)

    def __init__(self, *args, **kwargs):
        self.csv_data = None
        self.save_requests = None

        super().__init__(*args, **kwargs)

        # Folders can only be a destination for batch mode
        self.fields["source"].queryset = DicomNode.objects.filter(
            node_type=DicomNode.NodeType.SERVER, active=True
        )

        self.fields["destination"].queryset = DicomNode.objects.filter(active=True)

        self.fields["destination"].widget.attrs[
            "@change"
        ] = "destinationChanged($event)"

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"

        self.fields[
            "trial_protocol_id"
        ].help_text = """
            Fill only when to modify the ClinicalTrialProtocolID tag
            of all transfered DICOM files. Leave blank otherwise.
        """

        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"

        self.fields[
            "trial_protocol_name"
        ].help_text = """
            Fill only when to modify the ClinicalTrialProtocolName tag
            of all transfered DICOM files. Leave blank otherwise.
        """

        self.fields["archive_password"].widget.attrs["placeholder"] = "Optional"

        self.fields[
            "archive_password"
        ].help_text = """
            A password to download the DICOM files into an encrypted
            7z (https://7-zip.org) archive (max. 10 investigations). 
            Leave blank to not use an archive.
        """

        self.fields["csv_file"].label = "CSV file"

        self.fields[
            "csv_file"
        ].help_text = """
            The CSV file which contains the data to transfer between
            two DICOM nodes. See [help] how to format the CSV file.
        """

        self.helper = FormHelper(self)
        self.helper.attrs["x-data"] = "batchTransferForm()"
        self.helper.attrs["x-init"] = "init"

        self.helper["archive_password"].wrap(Div, x_show="isDestinationFolder")

        self.helper.add_input(Submit("save", "Create Job"))

    def clean_archive_password(self):
        archive_password = self.cleaned_data["archive_password"]
        destination = self.cleaned_data.get("destination")
        if destination and destination.node_type != DicomNode.NodeType.FOLDER:
            archive_password = ""
        return archive_password

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]

        delimiter = settings.BATCH_FILE_CSV_DELIMITER
        date_input_formats = formats.get_format("DATE_INPUT_FORMATS")
        parser = RequestParser(delimiter, date_input_formats)

        try:
            rawdata = csv_file.read()
            encoding = chardet.detect(rawdata)["encoding"]
            fp = StringIO(rawdata.decode(encoding))
            self.csv_data = parser.parse(fp)
        except ParsingError as err:
            for error in err.errors:
                self.add_error(None, error)
            raise ValidationError(err.message) from err

        return csv_file

    def _save_requests(self, batch_job):
        requests = []
        for row in self.csv_data:
            request = BatchTransferRequest(
                job=batch_job,
                request_id=row["RequestID"],
                patient_id=row["PatientID"],
                patient_name=row["PatientName"],
                patient_birth_date=row["PatientBirthDate"],
                study_date=row["StudyDate"],
                modality=row["Modality"],
                pseudonym=row["Pseudonym"],
            )
            requests.append(request)

        BatchTransferRequest.objects.bulk_create(requests)

    def save(self, commit=True):
        with transaction.atomic():
            batch_job = super().save(commit=commit)

            if commit:
                self._save_requests(batch_job)
            else:
                # If not committing, add a method to the form to allow deferred
                # saving of requests.
                self.save_requests = self._save_requests

        return batch_job

    class Meta:
        model = BatchTransferJob
        fields = (
            "source",
            "destination",
            "project_name",
            "project_description",
            "trial_protocol_id",
            "trial_protocol_name",
            "archive_password",
            "csv_file",
        )
