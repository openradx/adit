from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Layout,
    Fieldset,
    ButtonHolder,
    Submit,
    Field,
    Row,
    Column,
)


class QueryStudiesForm(forms.Form):
    patient_id = forms.CharField(max_length=64, required=False)
    patient_name = forms.CharField(max_length=256, required=False)
    patient_birth_date = forms.DateField(label="Birth date", required=False)
    study_date = forms.DateField(required=False)
    accession_number = forms.CharField(max_length=16, required=False)
    modality = forms.CharField(max_length=16, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column(Field("patient_id")),
                Column(Field("patient_name")),
                Column(Field("patient_birth_date")),
                Column(Field("study_date")),
                Column(Field("accession_number")),
                Column(Field("modality")),
                Column(Submit("search", "Search")),
            )
        )
        # self.helper.layout = ((Fieldset("Foobar", "patient_id")),)
        # ButtonHolder(Submit("submit", "Submit", css_class="button white"))
