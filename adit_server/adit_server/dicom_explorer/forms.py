from typing import cast

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from adit_server.core.fields import DicomNodeChoiceField
from adit_server.core.models import DicomNode
from adit_server.core.validators import (
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
    patient_id = forms.CharField(
        label="Patient ID",
        max_length=64,
        required=False,
        validators=id_validators,
    )
    accession_number = forms.CharField(
        label="Accession Number",
        max_length=32,
        required=False,
        validators=id_validators,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["server"] = DicomNodeChoiceField("source", self.user)

        self.helper = FormHelper(self)
        self.helper.form_id = "dicom_explorer"
        self.helper.form_method = "GET"
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-md-2"
        self.helper.field_class = "col-md-10"
        self.helper.add_input(Submit("query", "Query"))

    def clean_server(self):
        source = cast(DicomNode, self.cleaned_data["server"])
        if not source.is_accessible_by_user(self.user, "source"):
            raise ValidationError(_("You do not have access to this server."))
        return source
