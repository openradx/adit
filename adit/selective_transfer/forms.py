import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column, Div
from crispy_forms.bootstrap import StrictButton
from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode
from adit.core.utils.dicom_utils import person_name_to_dicom
from adit.core.validators import no_backslash_char_validator, no_control_chars_validator
from .models import SelectiveTransferJob


def server_field(field_name):
    return Column(
        Field(
            field_name,
            css_class="custom-select",
            **{"@change": "onServerChanged"},
        )
    )


def option_field(field_name, additional_attrs=None):
    attrs = {"@keydown.enter.prevent": ""}
    if additional_attrs:
        attrs = {**additional_attrs, **attrs}

    return Column(
        Field(
            field_name,
            **attrs,
        )
    )


def query_field(field_name):
    return Column(
        Field(
            field_name,
            **{"@keydown.enter.prevent": "submitQuery"},
        )
    )


class SelectiveTransferJobForm(forms.ModelForm):
    source = DicomNodeChoiceField(True, DicomNode.NodeType.SERVER)
    destination = DicomNodeChoiceField(False)
    pseudonym = forms.CharField(
        required=False,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
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
            "urgent",
            "trial_protocol_id",
            "trial_protocol_name",
            "pseudonym",
            "archive_password",
            "patient_id",
            "patient_name",
            "patient_birth_date",
            "study_date",
            "modality",
            "accession_number",
        )
        labels = {
            "urgent": "Start transfer directly",
            "trial_protocol_id": "Trial ID",
            "trial_protocol_name": "Trial name",
        }
        help_texts = {
            "urgent": (
                "Start transfer directly (without scheduling) and prioritize it."
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.query_form = kwargs.pop("query_form")

        super().__init__(*args, **kwargs)

        if not self.user.has_perm("selective_transfer.can_process_urgently"):
            del self.fields["urgent"]

        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                server_field("source"),
                server_field("destination"),
            ),
            Row(
                Column(
                    Field(
                        "urgent",
                        **{"@change": "onUrgencyChanged"},
                    ),
                ),
                css_class="pl-1",
            ),
            Row(
                Column(
                    Div(
                        Div(
                            StrictButton(
                                "Advanced transfer options (optional)",
                                css_class="btn-link px-0",
                                css_id="advanced_options_toggle",
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
                                option_field("trial_protocol_id"),
                                option_field("trial_protocol_name"),
                            ),
                            Row(
                                option_field("pseudonym"),
                                option_field(
                                    "archive_password",
                                    {":disabled": "!isDestinationFolder"},
                                ),
                            ),
                            css_class="show pt-1",
                            css_id="advanced_options",
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

    def clean_pseudonym(self):
        pseudonym = self.cleaned_data["pseudonym"]
        if not self.query_form:
            # We only validate if a pseudonym must be set if the user starts
            # to transfer and not when just querying for studies
            can_transfer_unpseudonymized = self.user.has_perm(
                "selective_transfer.can_transfer_unpseudonymized"
            )
            if not pseudonym and not can_transfer_unpseudonymized:
                raise ValidationError(_("This field is required."))
        return pseudonym

    def clean_archive_password(self):
        archive_password = self.cleaned_data["archive_password"]
        destination = self.cleaned_data.get("destination")
        if not destination or destination.node_type != DicomNode.NodeType.FOLDER:
            archive_password = ""
        return archive_password

    def clean_patient_name(self):
        patient_name = self.cleaned_data["patient_name"]
        return person_name_to_dicom(patient_name)

    def clean_modality(self):
        modality = self.cleaned_data["modality"]
        modilities = re.split(r"\s*,\s*", modality)

        if len(modilities) == 0:
            return ""
        if len(modilities) == 1:
            return modilities[0]
        return modilities
