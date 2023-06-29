from django import forms
import cchardet as chardet
from io import StringIO
import uuid
import os

from django.db import transaction
from django.core.exceptions import ValidationError
from adit.core.errors import BatchFileFormatError, BatchFileSizeError

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from adit.core.forms import DicomNodeChoiceField
from adit.core.fields import RestrictedFileField
from adit.core.models import DicomNode, DicomFolder
from .models import UploadJob, UploadTask
from .parsers import UploadBatchFileParser


class UploadJobForm(forms.ModelForm):
    source = forms.CharField(required=False)
    destination = DicomNodeChoiceField(False)
#    batch_file = RestrictedFileField(max_upload_size=5242880, label="Batch file")
    upload_files = RestrictedFileField(label="Upload files")
    upload_files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
    pseudonym = forms.CharField()

    class Meta:
        model = UploadJob
        fields = (
            "source",
            "destination",
            "project_name",
            "project_description",
            "pseudonym",
#            "batch_file",
            "upload_files",
            "trial_protocol_id",
            "trial_protocol_name",
        )
        labels = {
            "urgent": "Start upload urgently",
            "trial_protocol_id": "Trial ID",
            "trial_protocol_name": "Trial name",
        }
        help_texts = {
#            "batch_file": (
#                "The batch file which contains the pseudonyms for the upload. "
#                "See [Help] for how to format this file."
#            ),
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
        self.tasks = None
        self.save_tasks = None

        user = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        pathuid = str(uuid.uuid1())
        self.fields["source"].initial = pathuid
        #self.fields["source"].widget.attrs['readonly'] = 'readonly'
        self.fields["destination"].widget.attrs["class"] = "custom-select"

        self.fields["destination"].queryset = self.fields["destination"].queryset.order_by(
            "-node_type", "name"
        )

        self.max_batch_size = settings.MAX_BATCH_QUERY_SIZE if not user.is_staff else None

#        if self.max_batch_size is not None:
#            self.fields[
#                "batch_file"
#            ].help_text = f"Maximum {self.max_batch_size} tasks per query job!"

#        self.fields["batch_file"].required = False

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"
        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_source(self):
        folderpath = "upload" + self.cleaned_data["source"]
        source = DicomFolder(name=folderpath, path=folderpath)
        source.save()
        
        self.tasks = []
        # Todo find way to get the study uid on client side
        utask = UploadTask(task_id=1, patient_id="uploadtestptid", study_uid=folderpath)
        self.tasks.append(utask)

        return source
    
    # def clean_batch_file(self):
    #     batch_file = self.cleaned_data["batch_file"]
    #     rawdata = batch_file.read()
    #     encoding = chardet.detect(rawdata)["encoding"]

    #     if not encoding:
    #         raise ValidationError("Invalid batch file (unknown encoding).")

    #     file = StringIO(rawdata.decode(encoding))

    #     parser = BatchQueryFileParser()

    #     try:
    #         self.tasks = parser.parse(file, self.max_batch_size)

    #     except BatchFileSizeError as err:
    #         raise ValidationError(
    #             f"Too many batch tasks (max. {self.max_batch_size} tasks)"
    #         ) from err

    #     except BatchFileFormatError as err:
    #         self.batch_file_errors = err
    #         raise ValidationError(
    #             mark_safe(
    #                 "Invalid batch file. "
    #                 '<a href="#" data-toggle="modal" data-target="#batch_file_errors_modal">'
    #                 "[View details]"
    #                 "</a>"
    #             )
    #         ) from err
    #     return batch_file

    def _save_tasks(self, batch_job):
        for task in self.tasks:
            task.job = batch_job

        UploadTask.objects.bulk_create(self.tasks)

    def save(self, commit=True):
        with transaction.atomic():
            batch_job = super().save(commit=commit)

            if commit:
                self._save_tasks(batch_job)
            else:
                # If not committing, add a method to the form to allow deferred saving of tasks.
                self.save_tasks = self._save_tasks