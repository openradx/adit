from crispy_forms.bootstrap import FieldWithButtons, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout
from django import forms


class SearchForm(forms.Form):
    q = forms.CharField(label="", max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = "GET"
        self.helper.layout = Layout(
            FieldWithButtons(
                Field("q", placeholder="Search"),
                StrictButton(
                    "<i class='bi bi-search'></i>",
                    css_class="btn-success",
                    type="submit",
                ),
            ),
        )
