from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div, Hidden
from crispy_forms.bootstrap import FieldWithButtons


class FilterFormHelper(FormHelper):
    form_class = "form-inline"
    label_class = "mr-sm-2"
    field_template = "bootstrap4/layout/inline_field.html"

    def __init__(self, request, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.form_method = "get"
        self.disable_csrf = True

        query_fields = Div()
        for key in request.GET:
            if key != field_name:
                query_fields.append(Hidden(key, request.GET.get(key)))

        self.layout = Layout(
            query_fields,
            FieldWithButtons(
                Field(field_name, css_class="custom-select custom-select-sm"),
                Submit("", "Set", css_class="btn-sm"),
                css_class="input-group-sm",
            ),
        )
