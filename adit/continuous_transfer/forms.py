from django import forms
from crispy_forms.helper import FormHelper
from django.forms.models import BaseInlineFormSet
from .models import ContinuousTransferJob, DataElementFilter


class DateInput(forms.DateInput):
    input_type = "date"


class ContinuousTransferJobForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.disable_csrf = True

    class Meta:
        model = ContinuousTransferJob
        fields = (
            "source",
            "destination",
            "project_name",
            "project_description",
            "trial_protocol_id",
            "trial_protocol_name",
            "start_date",
            "end_date",
        )
        widgets = {"start_date": DateInput(), "end_date": DateInput()}


class DataElementFilterForm(forms.ModelForm):
    class Meta:
        model = DataElementFilter
        fields = ("dicom_tag", "filter_type", "filter_value", "case_sensitive")


class BaseDataElementFilterFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields[forms.formsets.ORDERING_FIELD_NAME].initial = index + 1


DataElementFilterFormSet = forms.inlineformset_factory(
    ContinuousTransferJob,
    DataElementFilter,
    formset=BaseDataElementFilterFormSet,
    form=DataElementFilterForm,
    extra=1,
    can_order=True,
)


class DataElementFilterFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = "continuous_transfer/data_element_filter_formset.html"
