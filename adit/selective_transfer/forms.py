import re
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column, Div, Button
from crispy_forms.bootstrap import StrictButton
from adit.selective_transfer.models import SelectiveTransferJob
from adit.main.models import DicomNode, TransferTask
from adit.main.validators import validate_pseudonym


def server_field(field_name):
    change = "updateCookie();"
    if field_name == "source":
        change += " reset(true);"

    return Column(
        Field(
            field_name,
            css_class="custom-select",
            **{"x-model": f"formData.{field_name}", "@change": change},
        )
    )


def query_field(field_name):
    return Column(
        Field(
            field_name,
            **{
                "x_model": f"formData.{field_name}",
                "@keydown.enter.prevent": "submitQuery",
            },
        )
    )


def option_field(field_name):
    return Column(
        Field(
            field_name,
            **{
                "x_model": f"formData.{field_name}",
                "@keydown.enter.prevent": "",
            },
        )
    )


class SelectiveTransferJobForm(forms.ModelForm):
    pseudonym = forms.CharField(
        required=False, max_length=64, validators=[validate_pseudonym]
    )
    patient_id = forms.CharField(required=False, max_length=64, label="Patient ID")
    patient_name = forms.CharField(required=False, max_length=324)
    patient_birth_date = forms.DateField(required=False, label="Birth date")
    study_date = forms.DateField(required=False)
    modality = forms.CharField(required=False, max_length=16)
    accession_number = forms.CharField(
        required=False, max_length=16, label="Accession #"
    )

    class Meta:
        model = SelectiveTransferJob
        fields = (
            "source",
            "destination",
            "trial_protocol_id",
            "trial_protocol_name",
            "archive_password",
            "patient_id",
            "patient_name",
            "patient_birth_date",
            "study_date",
            "modality",
            "accession_number",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source"].queryset = DicomNode.objects.filter(
            node_type=DicomNode.NodeType.SERVER, active=True
        )
        self.fields["destination"].queryset = DicomNode.objects.filter(active=True)

        self.fields["trial_protocol_id"].label = "Trial ID"
        self.fields["trial_protocol_name"].label = "Trial name"

        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                server_field("source"),
                server_field("destination"),
            ),
            Row(
                Column(
                    Div(
                        Div(
                            StrictButton(
                                "Advanced transfer options (optional)",
                                css_class="btn-link px-0",
                                **{
                                    "data-toggle": "collapse",
                                    "data-target": "#advanced_options",
                                    "aria-expanded": "true",
                                    "aria-controls": "advancedOptions",
                                },
                            ),
                            css_class="card-title mb-0",
                        ),
                        Div(
                            Row(
                                option_field("pseudonym"),
                                option_field("archive_password"),
                            ),
                            Row(
                                option_field("trial_protocol_id"),
                                option_field("trial_protocol_name"),
                            ),
                            css_class="show pt-1",
                            css_id="advanced_options",
                            **{"x-ref": "advancedOptions"},
                        ),
                        css_class="card-body p-2",
                    ),
                    css_class="card",
                ),
                css_class="px-1 mb-3",
            ),
            Row(
                query_field("patient_id"),
                query_field("patient_name"),
                query_field("patient_birth_date"),
                query_field("study_date"),
                query_field("modality"),
                query_field("accession_number"),
            ),
        )

    def clean_patient_name(self):
        patient_name = self.cleaned_data["patient_name"]
        return re.sub(r"\s*,\s*", "^", patient_name)
