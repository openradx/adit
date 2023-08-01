from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.safestring import mark_safe

from adit.core.errors import BatchFileContentError, BatchFileFormatError, BatchFileSizeError
from adit.core.fields import RestrictedFileField
from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode

from .models import BatchTransferJob, BatchTransferTask
from .parsers import BatchTransferFileParser


class BatchTransferJobForm(forms.ModelForm):
    source = DicomNodeChoiceField(True, DicomNode.NodeType.SERVER)
    destination = DicomNodeChoiceField(False)
    batch_file = RestrictedFileField(
        max_upload_size=5242880,
        label="Batch file",
        help_text=(
            "The Excel file (*.xlsx) which contains the data to transfer between "
            "two DICOM nodes. See [Help] for how to format this file."
        ),
    )
    max_batch_size: int | None = None
    tasks: list[BatchTransferTask]

    class Meta:
        model = BatchTransferJob
        fields = (
            "source",
            "destination",
            "urgent",
            "project_name",
            "project_description",
            "ethics_application_id",
            "batch_file",
            "trial_protocol_id",
            "trial_protocol_name",
            "send_finished_mail",
        )
        labels = {
            "urgent": "Start transfer urgently",
            "trial_protocol_id": "Trial ID",
            "trial_protocol_name": "Trial name",
            "ethics_application_id": "Ethics committee approval",
            "send_finished_mail": "Send Email when job is finished",
        }
        help_texts = {
            "urgent": ("Start transfer directly (without scheduling) and prioritize it."),
            "ethics_application_id": (
                "The identification number of the ethics application for this trial."
            ),
            "trial_protocol_id": (
                "Fill only when to modify the ClinicalTrialProtocolID tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "trial_protocol_name": (
                "Fill only when to modify the ClinicalTrialProtocolName tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
        }

    def __init__(self, *args, **kwargs):
        self.batch_file_errors = None
        self.tasks = []
        self.save_tasks = None

        self.user = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["source"].widget.attrs["class"] = "form-select"
        self.fields["destination"].widget.attrs["class"] = "form-select"

        if not self.user.has_perm("batch_transfer.can_process_urgently"):
            del self.fields["urgent"]

        self.fields["source"].queryset = self.fields["source"].queryset.order_by(
            "-node_type", "name"
        )
        self.fields["destination"].queryset = self.fields["destination"].queryset.order_by(
            "-node_type", "name"
        )

        if settings.ETHICS_COMMITTEE_APPROVAL_REQUIRED:
            self.fields["ethics_application_id"].required = True

        self.max_batch_size = settings.MAX_BATCH_TRANSFER_SIZE if not self.user.is_staff else None

        if self.max_batch_size is not None:
            self.fields[
                "batch_file"
            ].help_text = f"Maximum {self.max_batch_size} tasks per transfer job!"

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"
        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_batch_file(self):
        batch_file = self.cleaned_data["batch_file"]
        can_transfer_unpseudonymized = self.user.has_perm(
            "batch_transfer.can_transfer_unpseudonymized"
        )
        parser = BatchTransferFileParser(can_transfer_unpseudonymized)

        try:
            self.tasks = parser.parse(batch_file, self.max_batch_size)
        except BatchFileFormatError:
            raise ValidationError("Invalid Excel (.xlsx) file.")
        except BatchFileSizeError as err:
            raise ValidationError(
                f"Too many batch tasks (max. {self.max_batch_size} tasks)"
            ) from err
        except BatchFileContentError as err:
            self.batch_file_errors = err
            raise ValidationError(
                mark_safe(
                    "Invalid batch file. "
                    '<a href="#" data-bs-toggle="modal" data-bs-target="#batch_file_errors_modal">'
                    "[View details]"
                    "</a>"
                )
            ) from err

        return batch_file

    def _save_tasks(self, batch_job: BatchTransferJob):
        for task in self.tasks:
            task.job = batch_job

        BatchTransferTask.objects.bulk_create(self.tasks)

    def save(self, commit=True):
        with transaction.atomic():
            batch_job = super().save(commit=commit)

            if commit:
                self._save_tasks(batch_job)
            else:
                # If not committing, add a method to the form to allow deferred
                # saving of tasks.
                self.save_tasks = self._save_tasks

        return batch_job
