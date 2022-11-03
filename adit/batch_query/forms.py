from io import StringIO
from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import cchardet as chardet
from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode
from adit.core.fields import RestrictedFileField
from adit.core.errors import BatchFileSizeError, BatchFileFormatError
from .models import BatchQueryJob, BatchQueryTask
from .parsers import BatchQueryFileParser


class BatchQueryJobForm(forms.ModelForm):
    source = DicomNodeChoiceField(True, DicomNode.NodeType.SERVER)
    batch_file = RestrictedFileField(max_upload_size=5242880, label="Batch file")

    class Meta:
        model = BatchQueryJob
        fields = (
            "source",
            "urgent",
            "project_name",
            "project_description",
            "batch_file",
        )
        labels = {
            "urgent": "Start query urgently",
        }
        help_texts = {
            "urgent": ("Prioritize and start directly (without scheduling)."),
            "batch_file": (
                "The batch file which contains the data for the queries. "
                "See [Help] for how to format this file."
            ),
        }

    def __init__(self, *args, **kwargs):
        self.batch_file_errors = None
        self.tasks = None
        self.save_tasks = None

        user = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["source"].widget.attrs["class"] = "custom-select"

        if not user.has_perm("batch_query.can_process_urgently"):
            del self.fields["urgent"]

        self.fields["source"].queryset = self.fields["source"].queryset.order_by(
            "-node_type", "name"
        )

        self.max_batch_size = settings.MAX_BATCH_QUERY_SIZE if not user.is_staff else None

        if self.max_batch_size is not None:
            self.fields[
                "batch_file"
            ].help_text = f"Maximum {self.max_batch_size} tasks per query job!"

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_batch_file(self):
        batch_file = self.cleaned_data["batch_file"]
        rawdata = batch_file.read()
        encoding = chardet.detect(rawdata)["encoding"]

        if not encoding:
            raise ValidationError("Invalid batch file (unknown encoding).")

        file = StringIO(rawdata.decode(encoding))

        parser = BatchQueryFileParser()

        try:
            self.tasks = parser.parse(file, self.max_batch_size)

        except BatchFileSizeError as err:
            raise ValidationError(
                f"Too many batch tasks (max. {self.max_batch_size} tasks)"
            ) from err

        except BatchFileFormatError as err:
            self.batch_file_errors = err
            raise ValidationError(
                mark_safe(
                    "Invalid batch file. "
                    '<a href="#" data-toggle="modal" data-target="#batch_file_errors_modal">'
                    "[View details]"
                    "</a>"
                )
            ) from err

        return batch_file

    def _save_tasks(self, job):
        for task in self.tasks:
            task.job = job

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
