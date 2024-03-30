from typing import Literal, NamedTuple, cast

from crispy_forms.bootstrap import FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Hidden, Layout, Submit
from django import forms
from django.http.request import QueryDict


class BroadcastForm(forms.Form):
    subject = forms.CharField(label="Subject", max_length=200)
    message = forms.CharField(label="Message", max_length=10000, widget=forms.Textarea)


class PageSizeSelectForm(forms.Form):
    per_page = forms.ChoiceField(required=False, label="Items per page")

    def __init__(self, data, pages_sizes, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

        choices = [(size, size) for size in pages_sizes]
        per_page_field = cast(forms.ChoiceField, self.fields["per_page"])
        per_page_field.choices = choices

        # For simplicity we reuse the FilterSetFormHelper here (normally used for filters)
        form_helper = FilterSetFormHelper(data)
        form_helper.add_filter_field("per_page", "select", button_label="Set")
        form_helper.build_filter_set_layout()
        self.helper = form_helper


class FilterSetFormHelper(FormHelper):
    """All filters of one model are rendered in one form."""

    class FilterField(NamedTuple):
        field_name: str
        field_type: Literal["select", "text"]
        button_label: str = "Set"

    def __init__(
        self,
        params: QueryDict | dict,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.form_method = "get"
        self.disable_csrf = True

        self.params = params
        self.layout = Layout()
        self.filter_fields: list[FilterSetFormHelper.FilterField] = []

    def add_filter_field(
        self, field_name: str, field_type: Literal["select", "text"], button_label: str = "Set"
    ):
        self.filter_fields.append(
            FilterSetFormHelper.FilterField(field_name, field_type, button_label)
        )

    def build_filter_set_layout(self):
        field_names = []

        visible_fields = Div(css_class="d-flex gap-3")
        self.layout.append(visible_fields)

        for filter_field in self.filter_fields:
            field_names.append(filter_field.field_name)

            # TODO: FieldWithButtons do not work correctly with select widget, we
            # have to add the CSS class manually
            # https://github.com/django-crispy-forms/crispy-bootstrap5/issues/148
            if filter_field.field_type == "select":
                field_class = "form-select form-select-sm"
            else:
                field_class = "form-control-sm"

            visible_fields.append(
                FieldWithButtons(
                    Field(filter_field.field_name, css_class=field_class),
                    Submit(
                        "",
                        filter_field.button_label,
                        css_class="btn-secondary btn-sm",
                    ),
                    template="common/_filter_set_field.html",
                ),
            )

        hidden_fields = Div()
        self.layout.append(hidden_fields)

        for key in self.params:
            if key not in field_names:
                hidden_fields.append(Hidden(key, self.params.get(key)))
