from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from adit.core.models import DicomServer
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)

id_validators = [
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
]


class DicomExplorerQueryForm(forms.Form):
    server = forms.ModelChoiceField(queryset=DicomServer.objects.all())
    patient_id = forms.CharField(
        label="Patient ID",
        max_length=64,
        required=False,
        validators=id_validators,
    )
    accession_number = forms.CharField(
        label="Accession Number",
        max_length=16,
        required=False,
        validators=id_validators,
    )
    study_uid = forms.CharField(
        label="Study Instance UID",
        max_length=64,
        required=False,
        validators=id_validators,
    )
    series_uid = forms.CharField(
        label="Series Instance UID",
        max_length=64,
        required=False,
        validators=id_validators,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["server"].widget.attrs["class"] = "custom-select"

        self.helper = FormHelper(self)
        self.helper.form_id = "dicom_explorer"
        self.helper.form_method = "GET"
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-md-2"
        self.helper.field_class = "col-md-10"
        self.helper.add_input(Submit("query", "Query"))

    def clean(self):
        cleaned_data = super().clean()

        if not (
            cleaned_data.get("patient_id")
            or cleaned_data.get("accession_number")
            or cleaned_data.get("study_uid")
            or cleaned_data.get("series_uid")
        ):
            raise ValidationError("At least one ID or UID must be provided.")

        if cleaned_data.get("series_uid") and not (
            cleaned_data.get("accession_number") or cleaned_data.get("study_uid")
        ):
            raise ValidationError(
                "When using Series Instance UID also a Study Instance UID "
                " or Accession Number must be provided."
            )
