from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column
from selective_transfer.models import SelectiveTransferJob
from main.models import DicomNode


def create_field(field_name, send_query_on_enter=True):
    field_attrs = {"css_class": "query_field", "x_model": f"formData.{field_name}"}
    if send_query_on_enter:
        field_attrs["@keydown.enter.prevent"] = "submitQuery()"
    else:
        field_attrs["@keydown.enter.prevent"] = ""
    return Column(Field(field_name, **field_attrs))


class SelectiveTransferJobForm(forms.ModelForm):
    patient_id = forms.CharField(label="Patient ID", max_length=64, required=False)
    patient_name = forms.CharField(label="Patient Name", max_length=256, required=False)
    patient_birth_date = forms.DateField(label="Birth Date", required=False)
    study_date = forms.DateField(label="Study Date", required=False)
    modality = forms.CharField(max_length=16, required=False)
    accession_number = forms.CharField(
        label="Accession Number", max_length=16, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source"].queryset = DicomNode.objects.filter(
            node_type=DicomNode.NodeType.SERVER
        )

        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(create_field("source", False), create_field("destination", False)),
            Row(
                create_field("patient_id"),
                create_field("patient_name"),
                create_field("patient_birth_date"),
                create_field("study_date"),
                create_field("modality"),
                create_field("accession_number"),
            ),
        )

    class Meta:
        model = SelectiveTransferJob
        fields = ("source", "destination")
