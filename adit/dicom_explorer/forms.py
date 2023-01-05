from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row, Submit
from django import forms
from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode, DicomServer
from adit.core.validators import (
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
)
from adit.xnat_support.forms import xnat_options_field

id_validators = [
    no_backslash_char_validator,
    no_control_chars_validator,
    no_wildcard_chars_validator,
]


class DicomExplorerQueryForm(forms.Form):
    server = DicomNodeChoiceField(
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
    xnat_project_id = forms.CharField(
        label="XNAT Project ID",
        max_length=64,
        required=False,
        help_text="Providing a XNAT Project ID significantly loweres the query time.",
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

        self.helper.layout = Layout(
            Row(Column(Field("server", css_class="custom-select"))),
            xnat_options_field(["xnat_project_id"]),
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
        )
