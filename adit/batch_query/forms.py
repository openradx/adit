from io import StringIO
from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import cchardet as chardet
from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode
from adit.core.fields import RestrictedFileField
from adit.core.utils.batch_parsers import ParsingError
from .models import BatchQueryJob, BatchQueryTask
from .utils.batch_parsers import BatchQueryFileParser


class BatchQueryJobForm(forms.ModelForm):
    source = DicomNodeChoiceField(True, DicomNode.NodeType.SERVER)
    csv_file = RestrictedFileField(max_upload_size=5242880, label="CSV file")

    class Meta:
        model = BatchQueryJob
        fields = (
            "source",
            "urgent",
            "project_name",
            "project_description",
            "csv_file",
        )
        labels = {
            "urgent": "Start query urgently",
        }
        help_texts = {
            "urgent": ("Prioritize and start directly (without scheduling)."),
            "csv_file": (
                "The CSV file which contains the data for the queries. "
                "See [Help] how to format the CSV file."
            ),
        }

    def __init__(self, *args, **kwargs):
        self.csv_error_details = None
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

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        rawdata = csv_file.read()
        encoding = chardet.detect(rawdata)["encoding"]
        file = StringIO(rawdata.decode(encoding))
        parser = BatchQueryFileParser(
            {
                "task_id": "TaskID",
                "patient_id": "PatientID",
                "patient_name": "PatientName",
                "patient_birth_date": "PatientBirthDate",
                "accession_number": "AccessionNumber",
                "study_date_start": "From",
                "study_date_end": "Until",
                "modalities": "Modality",
                "pseudonym": "Pseudonym",
            },
        )

        try:
            self.tasks = parser.parse(file)
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
