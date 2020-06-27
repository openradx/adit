from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Submit
from .models import BatchTransferJob
from .fields import RestrictedFileField

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
        # TODO proccess excel file here and create items
        # use self.add_error to add multiple errors
        return file

    def save(self, commit=True):
        job = super().save(commit=commit)
        # TODO save job items here
        return job

    class Meta:
        model = BatchTransferJob
        fields=(
            'source', 'destination', 'project_name', 'project_description',
            'pseudonymize', 'trial_protocol_id', 'trial_protocol_name',
            'excel_file'
        )