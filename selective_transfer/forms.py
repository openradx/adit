from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column
from selective_transfer.models import SelectiveTransferJob
from main.models import DicomNode


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

        self.fields['source'].queryset = DicomNode.objects.filter(node_type=DicomNode.NodeType.SERVER)

        query_field_class = "query_field"
        self.helper = FormHelper()
        self.helper.form_id = "study_query_form"
        self.helper.layout = Layout(
            Row(Column(Field("source")), Column(Field("destination"))),
            Row(
                Column(Field("patient_id", css_class=query_field_class)),
                Column(Field("patient_name", css_class=query_field_class)),
                Column(Field("patient_birth_date", css_class=query_field_class)),
                Column(Field("study_date", css_class=query_field_class)),
                Column(Field("modality", css_class=query_field_class)),
                Column(Field("accession_number", css_class=query_field_class)),
            ),
        )

    class Meta:
        model = SelectiveTransferJob
        fields = ("source", "destination")
