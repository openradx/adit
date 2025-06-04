from typing import cast

from adit_radis_shared.accounts.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from adit.core.errors import BatchFileContentError, BatchFileFormatError, BatchFileSizeError
from adit.core.fields import DicomNodeChoiceField, RestrictedFileField
from adit.core.models import DicomNode

from .models import BatchTransferJob, BatchTransferTask
from .parsers import BatchTransferFileParser


class BatchTransferJobForm(forms.ModelForm):
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
            "urgent",
            "project_name",
            "project_description",
            "ethics_application_id",
            "batch_file",
            "trial_protocol_id",
            "trial_protocol_name",
            "send_finished_mail",
            "convert_to_nifti",
        )
        labels = {
            "trial_protocol_id": "Trial ID",
            "trial_protocol_name": "Trial name",
            "ethics_application_id": "Ethics committee approval",
            "send_finished_mail": "Send Email when job is finished",
            "convert_to_nifti": "Convert to NIfTI",
        }
        help_texts = {
            "urgent": ("Prioritize this transfer job."),
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

        self.user: User = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["source"] = DicomNodeChoiceField("source", self.user)
        self.fields["source"].widget.attrs["@change"] = "onSourceChange($event)"

        self.fields["destination"] = DicomNodeChoiceField("destination", self.user)
        self.fields["destination"].widget.attrs["@change"] = "onDestinationChange($event)"

        self.fields["urgent"].widget.attrs["@change"] = "onUrgentChange($event)"

        if not self.user.has_perm("batch_transfer.can_process_urgently"):
            del self.fields["urgent"]

        if settings.ETHICS_COMMITTEE_APPROVAL_REQUIRED:
            self.fields["ethics_application_id"].required = True

        self.max_batch_size = settings.MAX_BATCH_TRANSFER_SIZE if not self.user.is_staff else None

        if self.max_batch_size is not None:
            self.fields[
                "batch_file"
            ].help_text = f"Maximum {self.max_batch_size} tasks per transfer job!"

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"
        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"

        self.fields["send_finished_mail"].widget.attrs["@change"] = (
            "onSendFinishedMailChange($event)"
        )

        self.fields["convert_to_nifti"].widget.attrs["@change"] = "onConvertToNiftiChange($event)"

        self.helper = FormHelper(self)
        self.helper.layout = Layout("source", "destination")  # Make sure those fields are on top
        self.helper.render_unmentioned_fields = True  # and the rest of the fields below
        self.helper.attrs["x-data"] = "batchTransferJobForm()"
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_source(self):
        source = cast(DicomNode, self.cleaned_data["source"])
        if not source.is_accessible_by_user(self.user, "source"):
            raise ValidationError(_("You do not have access to this source."))
        return source

    def clean_destination(self):
        destination = cast(DicomNode, self.cleaned_data["destination"])
        if not destination.is_accessible_by_user(self.user, "destination"):
            raise ValidationError(_("You do not have access to this destination."))
        return destination

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
            # TODO: This can be removed later as source and destination will come from
            # the batch file
            task.source = self.cleaned_data["source"]
            task.destination = self.cleaned_data["destination"]

        BatchTransferTask.objects.bulk_create(self.tasks)

    def save(self, commit=True):
        batch_job = super().save(commit=commit)

        if commit:
            self._save_tasks(batch_job)
        else:
            # If not committing, add a method to the form to allow deferred
            # saving of tasks.
            self.save_tasks = self._save_tasks

        return batch_job
