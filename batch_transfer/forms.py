from django.forms import ModelForm
from django.db import transaction
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Submit
from .models import BatchTransferJob, BatchTransferRequest
from .fields import RestrictedFileField
from .utils.excel_processor import ExcelProcessor, ExcelError

class BatchTransferJobForm(ModelForm):
    excel_file = RestrictedFileField(max_upload_size=5242880)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')

        super().__init__(*args, **kwargs)

        if not self.user.has_perm('batch_transfer.can_transfer_unpseudonymized'):
            self.fields['pseudonymize'].widget.attrs['disabled'] = 'true'
            
            self.fields['pseudonymize'].help_text = """
                You only have the permission to transfer the data pseudonymized.
            """
        else:
            self.fields['pseudonymize'].help_text = """
                Should the transferred data be pseudonymized by providing the
                pseudonyms in the Excel file or by letting ADIT generate them.
            """

        self.fields['trial_protocol_id'].widget.attrs['placeholder'] = 'Optional'

        self.fields['trial_protocol_id'].help_text = """
            Fill only when to modify the ClinicalTrialProtocolID tag
            of all transfered DICOM files. Leave blank otherwise.
        """

        self.fields['trial_protocol_name'].widget.attrs['placeholder'] = 'Optional'

        self.fields['trial_protocol_name'].help_text = """
            Fill only when to modify the ClinicalTrialProtocolName tag
            of all transfered DICOM files. Leave blank otherwise.
        """

        self.fields['excel_file'].help_text = """
            The Excel file which contains the data to transfer between
            two DICOM nodes. See [help] how to format the Excel sheet.
        """

        self.helper = FormHelper()
        self.helper.add_input(Submit('save', 'Create new batch transfer job'))

    def clean_pseudonymize(self):
        pseudonymize = self.cleaned_data['pseudonymize']

        if not self.user.has_perm('batch_transfer.can_transfer_unpseudonymized'):
            pseudonymize = True

        return pseudonymize

    def clean_excel_file(self):
        file = self.cleaned_data['excel_file']

        try:
            processor = ExcelProcessor(file)
            self.excel_data = processor.extract_data()
        except ExcelError as err:
            for error in err.errors:
                self.add_error(None, error)
            raise ValidationError(str(err))

        return file

    def _save_requests(self, batch_job):
        requests = []
        for row in self.excel_data:
            request = BatchTransferRequest(
                job=batch_job, # TODO rename to batch_job
                request_id=row['RequestID'],
                patient_id=row['PatientID'],
                patient_name=row['PatientName'],
                patient_birth_date=row['PatientBirthDate'],
                study_date=row['StudyDate'],
                modality=row['Modality'],
                pseudonym=row['Pseudonym']
            )
            requests.append(request)
        
        BatchTransferRequest.objects.bulk_create(requests)

    def save(self, commit=True):
        with transaction.atomic():
            batch_job = super().save(commit=commit)

            if commit:
                self._save_requests(batch_job)
            else:
                # If not committing, add a method to the form to allow deferred
                # saving of requests.
                self.save_requests = self._save_requests

        return batch_job

    class Meta:
        model = BatchTransferJob
        fields=(
            'source', 'destination', 'project_name', 'project_description',
            'pseudonymize', 'trial_protocol_id', 'trial_protocol_name',
            'excel_file'
        )