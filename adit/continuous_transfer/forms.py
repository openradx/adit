from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Fieldset, Layout, Submit
from django import forms

from adit.core.forms import DicomNodeChoiceField
from adit.core.models import DicomNode

from .models import ContinuousTransferJob


class ContinuousTransferJobForm(forms.ModelForm):
    source = DicomNodeChoiceField(True, DicomNode.NodeType.SERVER)
    destination = DicomNodeChoiceField(False)

    class Meta:
        model = ContinuousTransferJob
        fields = (
            "source",
            "destination",
            "urgent",
            "project_name",
            "project_description",
            "trial_protocol_id",
            "trial_protocol_name",
            "study_date_start",
            "study_date_end",
            "patient_id",
            "patient_name",
            "patient_birth_date",
            "modalities",
            "study_description",
            "series_description",
            "series_numbers",
        )
        labels = {
            "urgent": "Start transfer urgently",
            "trial_protocol_id": "Trial ID",
            "trial_protocol_name": "Trial name",
            "study_date_end": "If not provided then the query will be open-ended",
            "patient_id": "Patient ID",
        }
        help_texts = {
            "urgent": ("Start transfer directly (without scheduling) and prioritize it."),
            "trial_protocol_id": (
                "Fill only when to modify the ClinicalTrialProtocolID tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "trial_protocol_name": (
                "Fill only when to modify the ClinicalTrialProtocolName tag "
                "of all transfered DICOM files. Leave blank otherwise."
            ),
            "modalities": "Multiple values can be separated by commas",
            "series_numbers": "Multiple values can be separated by commas",
        }
        widgets = {
            "study_date_start": forms.DateInput(attrs={"type": "date"}),
            "study_date_end": forms.DateInput(attrs={"type": "date"}),
            "patient_birth_date": forms.DateInput(attrs={"type": "date"}),
            "modalities": forms.TextInput(),
            "series_numbers": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["source"].widget.attrs["class"] = "custom-select"
        self.fields["destination"].widget.attrs["class"] = "custom-select"

        if not self.user.has_perm("continuous.can_process_urgently"):
            del self.fields["urgent"]

        self.fields["source"].queryset = self.fields["source"].queryset.order_by(
            "-node_type", "name"
        )
        self.fields["destination"].queryset = self.fields["destination"].queryset.order_by(
            "-node_type", "name"
        )

        self.fields["trial_protocol_id"].widget.attrs["placeholder"] = "Optional"
        self.fields["trial_protocol_name"].widget.attrs["placeholder"] = "Optional"

        self.helper = FormHelper(self)

        self.helper.layout = Layout(
            Field("source"),
            Field("destination"),
            Field("urgent"),
            Field("project_name"),
            Field("project_description"),
            Field("trial_protocol_id"),
            Field("trial_protocol_name"),
            Field("study_date_start"),
            Field("study_date_end"),
            Fieldset(
                "Query",
                "patient_id",
                "patient_name",
                "patient_birth_date",
                "modalities",
                "study_description",
                "series_description",
                "series_numbers",
            ),
            Submit("save", "Create Job"),
        )

    def clean_modalities(self):
        modalities = self.cleaned_data["modalities"]
        return map(lambda x: x.strip(), modalities.split(","))

    def clean_series_numbers(self):
        series_numbers = self.cleaned_data["series_numbers"]
        return map(lambda x: x.strip(), series_numbers.split(","))

    def clean(self):
        cleaned_data = super().clean()
        patient_id = cleaned_data["patient_id"].strip()
        patient_name = cleaned_data["patient_name"].strip()
        patient_birth_date = cleaned_data["patient_birth_date"]
        modalities = cleaned_data["modalities"]
        study_description = cleaned_data["study_description"].strip()
        series_description = cleaned_data["series_description"].strip()
        series_numbers = cleaned_data["series_numbers"]

        if not any(
            [
                patient_id,
                patient_name,
                patient_birth_date,
                modalities,
                study_description,
                series_description,
                series_numbers,
            ]
        ):
            raise forms.ValidationError(
                "At least one filter criteria must be provided: "
                "Patient ID, Patient Name, Patient Birth Date, Modalities, "
                "Study Description, Series Description or Series Numbers."
            )

        if patient_name and not patient_birth_date:
            raise forms.ValidationError(
                "Patient Birth Date must be provided when a Patient Name is provided."
            )

        return cleaned_data
