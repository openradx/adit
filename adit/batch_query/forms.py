from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.utils.safestring import mark_safe

from adit.core.errors import BatchFileContentError, BatchFileFormatError, BatchFileSizeError
from adit.core.fields import DicomNodeChoiceField, RestrictedFileField

from .models import BatchQueryJob, BatchQueryTask
from .parsers import BatchQueryFileParser


class BatchQueryJobForm(forms.ModelForm):
    batch_file = RestrictedFileField(
        max_upload_size=5242880,
        label="Batch file",
        help_text=(
            "The Excel file (*.xlsx) which contains the data for the queries. "
            "See [Help] for how to format this file."
        ),
    )
    tasks: list[BatchQueryTask]

    class Meta:
        model = BatchQueryJob
        fields = (
            "urgent",
            "project_name",
            "project_description",
            "batch_file",
            "send_finished_mail",
        )
        labels = {
            "urgent": "Start query urgently",
            "send_finished_mail": "Send Email when job is finished",
        }
        help_texts = {
            "urgent": ("Prioritize and start directly (without scheduling)."),
        }

    def __init__(self, *args, **kwargs):
        self.batch_file_errors = None
        self.tasks = []
        self.save_tasks = None

        user = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["source"] = DicomNodeChoiceField("source", user)
        self.fields["source"].widget.attrs["@change"] = "onSourceChange($event)"

        self.fields["urgent"].widget.attrs["@change"] = "onUrgentChange($event)"

        if not user.has_perm("batch_query.can_process_urgently"):
            del self.fields["urgent"]

        self.max_batch_size = settings.MAX_BATCH_QUERY_SIZE if not user.is_staff else None

        if self.max_batch_size is not None:
            self.fields[
                "batch_file"
            ].help_text = f"Maximum {self.max_batch_size} tasks per query job!"

        self.fields["send_finished_mail"].widget.attrs[
            "@change"
        ] = "onSendFinishedMailChange($event)"

        self.helper = FormHelper(self)
        self.helper.layout = Layout("source")  # Make sure source is on top
        self.helper.render_unmentioned_fields = True  # and the rest of the fields below
        self.helper.attrs["x-data"] = "batchQueryJobForm()"
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_batch_file(self):
        batch_file: File = self.cleaned_data["batch_file"]
        parser = BatchQueryFileParser()

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

    def _save_tasks(self, job):
        for task in self.tasks:
            task.job = job
            task.source = self.cleaned_data["source"]

        BatchQueryTask.objects.bulk_create(self.tasks)

    def save(self, commit=True):
        with transaction.atomic():
            job = super().save(commit=commit)

            if commit:
                self._save_tasks(job)
            else:
                # If not committing, add a method to the form to allow deferred
                # saving of query tasks.
                self.save_tasks = self._save_tasks

        return job
