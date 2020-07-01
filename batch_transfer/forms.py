from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Submit
from .models import BatchTransferJob, BatchTransferItem
from .fields import RestrictedFileField
from .utils.excel_processor import ExcelProcessor, ExcelError

class BatchTransferJobForm(forms.ModelForm):
    excel_file = RestrictedFileField(max_upload_size=5242880)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['trial_protocol_id'].help_text = """
            Optional to set ClinicalTrialProtocolID in all transfered
            DICOM headers. Leave blank to no modify this DICOM tag.
        """

        self.fields['trial_protocol_name'].help_text = """
            Optional to set ClinicalTrialProtocolName in all transfered
            DICOM headers. Leave blank to no modify this DICOM tag.
        """

        self.fields['excel_file'].help_text = """
            The Excel file which contains the data to transfer between
            two DICOM nodes. See [help] how to format the Excel sheet.
        """

        self.helper = FormHelper()
        self.helper.add_input(Submit('save', 'Create new job'))

    def clean_excel_file(self):
        file = self.cleaned_data['excel_file']

        try:
            processor = ExcelProcessor(file)
            self.excel_data = processor.extract_data()
        except ExcelError as err:
            for error in err.errors:
                self.add_error(error)
            raise ValidationError(str(err))

        return file

    def _save_items(self, job):
        items = []
        for row in self.excel_data:
            item = BatchTransferItem(
                job=job,
                row_id=row['RowID'],
                patient_id=row['PatientID'],
                patient_name=row['PatientName'],
                patient_birth_date=row['PatientBirthDate'],
                study_date=row['StudyDate'],
                modality=row['Modality'],
                pseudonym=row['Pseudonym']
            )
            items.append(item)
        
        BatchTransferItem.objects.bulk_create(items)

    def save(self, commit=True):
        with transaction.atomic():
            job = super().save(commit=commit)

            if commit:
                self._save_items(job)
            else:
                # If not committing, add a method to the form to allow deferred
                # saving of items.
                self.save_items = self._save_items

        return job

    class Meta:
        model = BatchTransferJob
        fields=(
            'source', 'destination', 'project_name', 'project_description',
            'pseudonymize', 'trial_protocol_id', 'trial_protocol_name',
            'excel_file'
        )