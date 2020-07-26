from django import forms

class QueryStudiesForm(forms.Form):
    patient_id = forms.CharField(max_length=64, required=False)
    patient_name = forms.CharField(max_length=256, required=False)
    patient_birth_date = forms.DateField(label='Birth date', required=False)
    study_date = forms.DateField(required=False)
    accession_number = forms.CharField(max_length=16, required=False)
    modality = forms.CharField(max_length=16, required=False)
    