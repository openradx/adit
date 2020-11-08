from io import StringIO
from django.forms import ModelForm
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import formats
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import cchardet as chardet
from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode
from .models import BatchTransferJob, BatchTransferRequest
from .fields import RestrictedFileField
from .utils.parsers import RequestsParser, ParsingError


class BatchTransferJobForm(ModelForm):
    source = DicomNodeChoiceField(DicomNode.NodeType.SERVER)
    destination = DicomNodeChoiceField()
    csv_file = RestrictedFileField(max_upload_size=5242880, label="CSV file")

    class Meta:
        model = BatchTransferJob
        fields = (
            "source",
            "destination",
            "project_name",
            "project_description",
            "trial_protocol_id",
            "trial_protocol_name",
            "csv_file",
        )
        labels = {
            "trial_protocol_id": "Trial ID",
            "trial_protocol_name": "Trial name",
        }
        help_texts = {
            "trial_protocol_id": (
                "Fill only when to modify the ClinicalTrialProtocolID tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "trial_protocol_name": (
                "Fill only when to modify the ClinicalTrialProtocolName tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "csv_file": (
                "The CSV file which contains the data to transfer between "
                "two DICOM nodes. See [help] how to format the CSV file."
            ),
        }

    def __init__(self, *args, **kwargs):
        self.csv_error_details = None
        self.requests = None
        self.save_requests = None

        super().__init__(*args, **kwargs)

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"
        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"

        self.helper = FormHelper(self)
        self.helper.attrs["x-data"] = "batchTransferForm()"

        self.helper.add_input(Submit("save", "Create Job"))

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]

        delimiter = settings.BATCH_FILE_CSV_DELIMITER
        date_input_formats = formats.get_format("DATE_INPUT_FORMATS")
        parser = RequestsParser(delimiter, date_input_formats)

        try:
            rawdata = csv_file.read()
            encoding = chardet.detect(rawdata)["encoding"]
            fp = StringIO(rawdata.decode(encoding))
            self.requests = parser.parse(fp)
        except ParsingError as err:
            self.csv_error_details = err
            raise ValidationError(
                mark_safe(
                    "Invalid format of CSV file. "
                    '<a href="#" data-toggle="modal" data-target="#csv_error_details_modal">'
                    "[View details]"
                    "</a>"
                )
            ) from err

        return csv_file

    def _save_requests(self, batch_job):
        for request in self.requests:
            request.job = batch_job

        BatchTransferRequest.objects.bulk_create(self.requests)

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
