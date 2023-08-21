import re

from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, Field, Layout, Row
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from adit.core.fields import DicomNodeChoiceField
from adit.core.models import DicomNode
from adit.core.utils.dicom_utils import person_name_to_dicom
from adit.core.validators import no_backslash_char_validator, no_control_chars_validator

from .models import SelectiveTransferJob


class SelectiveTransferJobForm(forms.ModelForm):
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
    accession_number = forms.CharField(required=False, max_length=32, label="Accession #")

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
            "send_finished_mail",
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
            "send_finished_mail": "Send Email when job is finished",
        }
        help_texts = {
            "urgent": ("Start transfer directly (without scheduling) and prioritize it."),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.action = kwargs.pop("action")
        self.advanced_options_collapsed = kwargs.pop("advanced_options_collapsed")

        super().__init__(*args, **kwargs)

        if not self.user.has_perm("selective_transfer.can_process_urgently"):
            del self.fields["urgent"]

        self.fields["source"] = DicomNodeChoiceField("source", self.user)
        self.fields["destination"] = DicomNodeChoiceField("destination", self.user)

        self.helper = FormHelper(self)
        self.helper.form_tag = False

        query_form_layout = self.build_query_form_layout()

        # We swap the form using the htmx alpine-morph extension to retain the focus on the input
        self.helper.layout = Layout(
            Div(query_form_layout, css_id="query_form", **{"hx-swap-oob": "morph"})
        )

    def clean_pseudonym(self):
        pseudonym = self.cleaned_data["pseudonym"]
        if self.action == "transfer":
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
        return person_name_to_dicom(patient_name, add_wildcards=True)

    def clean_modality(self):
        modality = self.cleaned_data["modality"]
        modilities = re.split(r"\s*,\s*", modality)

        if len(modilities) == 0:
            return ""
        if len(modilities) == 1:
            return modilities[0]
        return modilities

    def build_query_form_layout(self):
        query_form_layout = Layout(
            Row(
                Column(
                    Field(
                        "source",
                        **{"@change": "onSourceChange($event)"},
                    )
                ),
                Column(
                    Field(
                        "destination",
                        **{
                            "x-init": "initDestination($el)",
                            "@change": "onDestinationChange($event)",
                        },
                    )
                ),
            ),
            Row(
                Column(
                    self.build_advanced_options_layout(),
                    css_class="card",
                ),
                css_class="px-1 mb-3",
            ),
            Row(
                self.build_search_inputs_layout(),
            ),
        )

        if "urgent" in self.fields:
            query_form_layout.insert(
                1,
                Row(
                    Column(Field("urgent", **{"@change": "onUrgentChange($event)"})),
                    css_class="ps-1",
                ),
            )

        return query_form_layout

    def build_advanced_options_layout(self):
        if self.advanced_options_collapsed:
            aria_expanded = "false"
            advanced_options_class = "pt-1 collapse"
        else:
            aria_expanded = "true"
            advanced_options_class = "pt-1 collapse show"

        return Layout(
            Div(
                Div(
                    StrictButton(
                        "Advanced options",
                        css_class="btn-link px-0",
                        css_id="advanced_options_toggle",
                        **{
                            "data-bs-toggle": "collapse",
                            "data-bs-target": "#advanced_options",
                            "aria-expanded": aria_expanded,
                            "aria-controls": "advanced_options",
                        },
                    ),
                    css_class="card-title mb-0",
                ),
                Div(
                    Row(
                        self.build_option_field("trial_protocol_id"),
                        self.build_option_field("trial_protocol_name"),
                    ),
                    Row(
                        self.build_option_field("pseudonym"),
                        self.build_option_field(
                            "archive_password",
                            {":disabled": "!isDestinationFolder"},
                        ),
                    ),
                    Row(
                        self.build_option_field(
                            "send_finished_mail",
                            {"@change": "onSendFinishedMailChange($event)"},
                        ),
                    ),
                    css_class=advanced_options_class,
                    css_id="advanced_options",
                ),
                css_class="card-body p-2",
            ),
        )

    def build_option_field(self, field_name, additional_attrs=None):
        attrs = {"@keydown.enter.prevent": ""}
        if additional_attrs:
            attrs = {**additional_attrs, **attrs}

        return Column(Field(field_name, **attrs))

    def build_search_inputs_layout(self):
        return Layout(
            self.build_query_field("patient_id"),
            self.build_query_field("patient_name"),
            self.build_query_field("patient_birth_date"),
            self.build_query_field("study_date"),
            self.build_query_field("modality"),
            self.build_query_field("accession_number"),
        )

    def build_query_field(self, field_name):
        return Column(Field(field_name))
