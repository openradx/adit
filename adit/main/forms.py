from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field
from crispy_forms.bootstrap import FieldWithButtons


class FilterFormHelper(FormHelper):
    form_class = "form-inline"
    label_class = "mr-sm-2"
    field_template = "bootstrap4/layout/inline_field.html"

    def __init__(self, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "get"
        self.disable_csrf = True
        self.form_action = ""
        self.layout = Layout(
            FieldWithButtons(
                Field(field_name, css_class="form-control-sm"),
                Submit("filter", "Filter", css_class="btn-sm"),
            )
        )
