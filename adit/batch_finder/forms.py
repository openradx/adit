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
from adit.core.utils.parsers import BatchTaskParser, BatchTaskParserError
from .models import BatchFinderJob, BatchFinderQuery
from .serializers import BatchFinderQuerySerializer


class BatchFinderJobForm(forms.ModelForm):
    source = DicomNodeChoiceField(True, DicomNode.NodeType.SERVER)
    csv_file = RestrictedFileField(max_upload_size=5242880, label="CSV file")

    class Meta:
        model = BatchFinderJob
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
        self.queries = None
        self.save_queries = None

        urgent_option = kwargs.pop("urgent_option", False)

        super().__init__(*args, **kwargs)

        self.fields["source"].widget.attrs["class"] = "custom-select"

        if not urgent_option:
            del self.fields["urgent"]

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        parser = BatchTaskParser(
            BatchFinderQuerySerializer,
            {
                "batch_id": "Batch ID",
                "patient_id": "Patient ID",
                "patient_name": "Patient Name",
                "patient_birth_date": "Birth Date",
                "study_date_start": "From",
                "study_date_end": "Until",
                "modalities": "Modalities",
            },
        )

        try:
            rawdata = csv_file.read()
            encoding = chardet.detect(rawdata)["encoding"]
            fp = StringIO(rawdata.decode(encoding))
            self.queries = parser.parse(fp)
        except BatchTaskParserError as err:
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

    def _save_queries(self, job):
        for query in self.queries:
            query.job = job

        BatchFinderQuery.objects.bulk_create(self.queries)

    def save(self, commit=True):
        with transaction.atomic():
            job = super().save(commit=commit)

            if commit:
                self._save_queries(job)
            else:
                # If not committing, add a method to the form to allow deferred
                # saving of queries.
                self.save_queries = self._save_queries

        return job
