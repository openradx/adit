from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column
from selective_transfer.models import SelectiveTransferJob
from main.models import DicomNode


def create_field(field_name):
    return Column(
        Field(
            field_name,
            **{"x_model": f"formData.{field_name}", "@change": "updateCookie"},
        )
    )


class SelectiveTransferJobForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source"].queryset = DicomNode.objects.filter(
            node_type=DicomNode.NodeType.SERVER
        )

        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(create_field("source"), create_field("destination"))
        )

    class Meta:
        model = SelectiveTransferJob
        fields = ("source", "destination")
