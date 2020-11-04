from io import StringIO
from django.forms import ModelForm, ModelChoiceField
from django.forms.widgets import Select
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import formats
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Div
import cchardet as chardet
from adit.core.models import DicomNode
from .models import BatchTransferJob, BatchTransferRequest
from .fields import RestrictedFileField
from .utils.parsers import RequestsParser, ParsingError


class DicomNodeSelect(Select):
    def create_option(  # pylint: disable=too-many-arguments
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if hasattr(value, "instance"):
            dicom_node = value.instance
            if dicom_node.node_type == DicomNode.NodeType.SERVER:
                option["attrs"]["data-node_type"] = "server"
            elif dicom_node.node_type == DicomNode.NodeType.FOLDER:
                option["attrs"]["data-node_type"] = "folder"

        return option


class BatchTransferJobForm(ModelForm):
    source = ModelChoiceField(
        # Only servers can be a source of a transfer
        queryset=DicomNode.objects.filter(
            node_type=DicomNode.NodeType.SERVER, active=True
        ),
        widget=DicomNodeSelect,
    )
    destination = ModelChoiceField(
        queryset=DicomNode.objects.filter(active=True),
        widget=DicomNodeSelect,
    )
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
            "archive_password",
            "csv_file",
        )
        labels = {"trial_protocol_id": "Trial protocol ID"}
        help_texts = {
            "trial_protocol_id": (
                "Fill only when to modify the ClinicalTrialProtocolID tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "trial_protocol_name": (
                "Fill only when to modify the ClinicalTrialProtocolName tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "archive_password": (
                "A password to download the DICOM files into an encrypted "
                "7z (https://7-zip.org) archive (max. 10 investigations). "
                "Leave blank to not use an archive."
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

        self.fields["destination"].widget.attrs[
            "@change"
        ] = "destinationChanged($event)"

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"
        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"
        self.fields["archive_password"].widget.attrs["placeholder"] = "Optional"

        self.helper = FormHelper(self)
        self.helper.attrs["x-data"] = "batchTransferForm()"

        self.helper["archive_password"].wrap(Div, x_show="isDestinationFolder")

        self.helper.add_input(Submit("save", "Create Job"))

    def clean_archive_password(self):
        archive_password = self.cleaned_data["archive_password"]
        destination = self.cleaned_data.get("destination")
        if not destination or destination.node_type != DicomNode.NodeType.FOLDER:
            archive_password = ""
        return archive_password

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
