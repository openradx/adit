from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div, Hidden
from crispy_forms.bootstrap import FieldWithButtons


class PageSizeSelectForm(forms.Form):
    per_page = forms.ChoiceField(required=False, label="Items per page")

    def __init__(self, data, pages_sizes, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        choices = [(size, size) for size in pages_sizes]
        self.fields["per_page"].choices = choices
        print(dir(self.fields["per_page"]))

        self.helper = FormHelper()
        self.helper.form_method = "get"
        self.helper.disable_csrf = True
        self.helper.form_class = "form-inline"
        self.helper.label_class = "mr-sm-2"
        self.helper.field_template = "bootstrap4/layout/inline_field.html"

        query_fields = Div()
        for key in data:
            if key != "per_page":
                query_fields.append(Hidden(key, data.get(key)))

        self.helper.layout = Layout(
            query_fields,
            FieldWithButtons(
                Field("per_page", css_class="custom-select custom-select-sm"),
                Submit("", "Set", css_class="btn-secondary btn-sm"),
                css_class="input-group-sm",
            ),
        )


class FilterFormHelper(FormHelper):
    form_class = "form-inline"
    label_class = "mr-sm-2"
    field_template = "bootstrap4/layout/inline_field.html"

    def __init__(self, data, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "get"
        self.disable_csrf = True

        query_fields = Div()
        for key in data:
            if key != field_name:
                query_fields.append(Hidden(key, data.get(key)))

        self.layout = Layout(
            FieldWithButtons(
                Field(field_name, css_class="custom-select custom-select-sm"),
                Submit("", "Set", css_class="btn-secondary btn-sm"),
                css_class="input-group-sm",
            ),
            query_fields,
        )
