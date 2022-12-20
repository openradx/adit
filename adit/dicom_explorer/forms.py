from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
# from adit.core.models import DicomServer
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)
from ..core.models import DicomNode

id_validators = [
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
]


class DicomExplorerQueryForm(forms.Form):
    # server = forms.ModelChoiceField(queryset=DicomServer.objects.all())
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

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.user = user
        myquery = []
        for gruppe in self.user.groups.all():
            accesses = gruppe.GroupAccess.filter(access_type="src")
            for access in accesses.all():
                myquery.append(access.node.name)
        myNodes = DicomNode.objects.filter(name__in=myquery)
        queryset = myNodes
        self.fields["server"] = forms.ModelChoiceField(queryset=queryset)
        self.fields["server"].widget.attrs["class"] = "custom-select"

        self.helper = FormHelper(self)
        self.helper.form_id = "dicom_explorer"
        self.helper.form_method = "GET"
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-md-2"
        self.helper.field_class = "col-md-10"
        self.helper.add_input(Submit("query", "Query"))
