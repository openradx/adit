from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Row, Column, Div
from crispy_forms.bootstrap import StrictButton

from adit.xnat_support.forms import xnat_options_field
from adit.core.models import DicomServer, DicomNode
from adit.core.forms import DicomNodeChoiceField
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
    source = DicomNodeChoiceField(
        True, 
        DicomNode.NodeType.SERVER, 
    )
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

    # (optional) XNAT
    project_id = forms.CharField(
        label="XNAT Project ID",
        max_length=64,
        required=False,
    )
    experiment_id = forms.CharField(
        label="XNAT Experiment ID",
        max_length=64,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source"].widget.attrs["class"] = "custom-select"

        self.helper = FormHelper(self)
        self.helper.form_id = "dicom_explorer"
        self.helper.form_method = "GET"
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-md-2"
        self.helper.field_class = "col-md-10"
        self.helper.add_input(Submit("query", "Query"))

        self.helper.layout = Layout(
            Row(Column(Field("source", css_class="custom-select"))),
            Row(
                Column(
                    Field(
                        "patient_id",
                    )
                )
            ),
            Row(
                Column(
                    Field(
                        "accession_number",
                    )
                )
            ),
            xnat_options_field(["project_id", "experiment_id"]),
        )
