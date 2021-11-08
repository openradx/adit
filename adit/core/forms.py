from django import forms
from django.forms.models import ModelChoiceField
from django.forms.widgets import Select
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div, Hidden
from crispy_forms.bootstrap import FieldWithButtons
from .models import DicomNode


class BroadcastForm(forms.Form):
    subject = forms.CharField(label="Subject", max_length=200)
    message = forms.CharField(label="Message", max_length=10000, widget=forms.Textarea)


class DicomNodeSelect(Select):
    def create_option(  # pylint: disable=too-many-arguments
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if hasattr(value, "instance"):
            dicom_node = value.instance
            if dicom_node.node_type == DicomNode.NodeType.SERVER:
                option["attrs"]["data-node_type"] = "server"
            elif dicom_node.node_type == DicomNode.NodeType.FOLDER:
                option["attrs"]["data-node_type"] = "folder"

        return option


class DicomNodeChoiceField(ModelChoiceField):
    def __init__(self, source, node_type=None):
        if source:
            queryset = DicomNode.objects.filter(source_active=True)
        else:
            queryset = DicomNode.objects.filter(destination_active=True)

        if node_type and node_type in dict(DicomNode.NodeType.choices):
            queryset = queryset.filter(node_type=node_type)
        elif node_type is not None:
            raise AssertionError(f"Invalid node type: {node_type}")

        super().__init__(queryset=queryset, widget=DicomNodeSelect)


class PageSizeSelectForm(forms.Form):
    per_page = forms.ChoiceField(required=False, label="Items per page")

    def __init__(self, data, pages_sizes, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

        choices = [(size, size) for size in pages_sizes]
        self.fields["per_page"].choices = choices

        self.helper = SingleFilterFormHelper(
            data,
            "per_page",
            button_label="Set",
            button_id="set_page_size",
            at_url_end=True,
        )


class SingleFilterFormHelper(FormHelper):
    form_class = "form-inline"
    label_class = "mr-1"

    def __init__(self, data, field_name, select_widget=True, custom_style="", **kwargs):
        button_label = kwargs.pop("button_label", "Filter")
        button_id = kwargs.pop("button_id", "filter")
        at_url_end = kwargs.pop("at_url_end", False)

        super().__init__(**kwargs)

        self.form_method = "get"
        self.disable_csrf = True

        layout = Layout()

        if select_widget:
            css_class = "custom-select custom-select-sm"
        else:
            css_class = "form-control-sm"

        layout.append(
            FieldWithButtons(
                Field(field_name, css_class=css_class, style=custom_style),
                Submit(
                    "",
                    button_label,
                    css_class="btn-secondary btn-sm",
                    css_id=button_id,
                ),
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

        layout.append(
            Submit(
                "",
                "Filter",
                css_class="btn-secondary btn-sm ml-1",
                css_id="filter",
            )
        )

        self.layout = layout
