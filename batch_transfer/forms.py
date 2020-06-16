from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Submit, Button
from .models import BatchTransferJob


class BatchTransferJobForm(forms.ModelForm):
    excel_file = forms.FileField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('save', 'Add job'))

    class Meta:
        model = BatchTransferJob
        fields=['source', 'destination', 'project_name', 'project_description']