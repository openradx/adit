from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Submit
from .models import BatchTransferJob

class BatchTransferJobForm(forms.ModelForm):
    excel_file = forms.FileField()

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

    def save(self, commit=True):
        print('in save')
        return super().save(commit=commit)

    class Meta:
        model = BatchTransferJob
        fields=(
            'source', 'destination', 'project_name', 'project_description',
            'pseudonymize', 'trial_protocol_id', 'trial_protocol_name',
            'excel_file'
        )