from crispy_forms.bootstrap import AppendedText
from crispy_forms.helper import FormHelper
from crispy_forms.layout import BaseInput, Column, Div, Field, Layout, Row
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.utils.safestring import mark_safe

from adit.core.errors import BatchFileContentError, BatchFileFormatError, BatchFileSizeError
from adit.core.fields import DicomNodeChoiceField
from adit.core.models import DicomNode
from adit.core.validators import no_backslash_char_validator, no_control_chars_validator

from .models import UploadJob


class MultipleFileInput(forms.widgets.FileInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs["onchange"] = "chooseFolder(event)"
        attrs["webkitdirectory"] = True
        attrs["directory"] = True
        attrs["multiple"] = True
        super().__init__(attrs)


class UploadJobForm(forms.ModelForm):
    pseudonym = forms.CharField(
        required=True,
        max_length=64,
        validators=[no_backslash_char_validator, no_control_chars_validator],
    )
    # maybe instead this: https://github.com/Chive/django-multiupload?
    # file_selector = MultipleFileInput()
    data_folder_path = forms.CharField()

    class Meta:
        model = UploadJob
        fields = ("pseudonym", "data_folder_path")
        labels = {"pseudonym": "Patient Pseudonym"}  # , "data_folder_path": "Data Folder Path"}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.action = kwargs.pop("action")
        # self.instance = kwargs.pop("instance")

        super().__init__(*args, **kwargs)

        self.fields["destination"] = DicomNodeChoiceField("destination", self.user)

        self.helper = FormHelper(self)
        query_form_layout = self.build_query_form_layout()

        # We swap the form using the htmx alpine-morph extension to retain the focus on the input
        self.helper.layout = Layout(
            Div(query_form_layout, css_id="query_form", **{"hx-swap-oob": "morph"})
        )

    def build_query_form_layout(self):
        query_form_layout = Layout(
            Row(
                Column(self.build_option_field("pseudonym")),
                Column(
                    Field(
                        "destination",
                        **{
                            "x-init": "initDestination($el)",
                            "@change": "onDestinationChange($event)",
                        },
                    )
                ),
            ),
            Row(self.build_option_field("data_folder_path")),
        )

        return query_form_layout

    def build_option_field(self, field_name, additional_attrs=None):
        attrs = {"@keydown.enter.prevent": ""}
        if additional_attrs:
            attrs = {**additional_attrs, **attrs}

        # BaseInput("fileSelector", css_id="fileselector", value="", kwargs={"type": "file"})

        return Column(Field(field_name, **attrs))
