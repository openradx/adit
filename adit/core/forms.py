from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Button, Layout, Submit, Field, Div, Hidden
from crispy_forms.bootstrap import FieldWithButtons


class PageSizeSelectForm(forms.Form):
    per_page = forms.ChoiceField(required=False, label="Items per page")

    def __init__(self, data, pages_sizes, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

        choices = [(size, size) for size in pages_sizes]
        self.fields["per_page"].choices = choices

        self.helper = SingleFilterFormHelper(
            data, "per_page", button_label="Set", at_url_end=True
        )


class SingleFilterFormHelper(FormHelper):
    form_class = "form-inline"
    label_class = "mr-1"

    def __init__(self, data, field_name, *args, **kwargs):
        button_label = kwargs.pop("button_label", "Filter")
        at_url_end = kwargs.pop("at_url_end", False)

        super().__init__(*args, **kwargs)

        self.form_method = "get"
        self.disable_csrf = True

        layout = Layout()

        layout.append(
            FieldWithButtons(
                Field(field_name, css_class="custom-select custom-select-sm"),
                Submit("", button_label, css_class="btn-secondary btn-sm"),
                css_class="input-group-sm",
            ),
        )

        hidden_fields = Div()
        for key in data:
            if key != field_name:
                hidden_fields.append(Hidden(key, data.get(key)))

        if at_url_end:
            layout.insert(0, hidden_fields)
        else:
            layout.append(hidden_fields)

        self.layout = layout


class MultiInlineFilterFormHelper(FormHelper):
    form_class = "form-inline"
    label_class = "mr-1"

    def __init__(self, data, field_names, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "get"
        self.disable_csrf = True

        layout = Layout()

        for idx, field_name in enumerate(field_names):
            wrapper_class = "ml-2" if idx > 0 else ""
            layout.append(
                Field(
                    field_name,
                    template="core/_multi_inline_filter_field.html",
                    wrapper_class=wrapper_class,
                )
            )

        for key in data:
            if key not in field_names:
                layout.append(Hidden(key, data.get(key)))

        layout.append(Submit("", "Filter", css_class="btn-secondary btn-sm ml-1"))

        self.layout = layout
