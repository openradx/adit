from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column
from adit.selective_transfer.models import SelectiveTransferJob
from adit.main.models import DicomNode, DicomServer


class SelectiveTransferJobForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source"].queryset = DicomServer.objects.filter(active=True)
        self.fields["destination"].queryset = DicomNode.objects.filter(
            active=True
        ).select_subclasses()

        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(
                    Field(
                        "source",
                        **{
                            "x_model": "formData.source",
                            "@change": "updateCookie(); reset(true)",
                        },
                    )
                ),
                Column(
                    Field(
                        "destination",
                        **{
                            "x_model": "formData.destination",
                            "@change": "updateCookie",
                        },
                    )
                ),
            )
        )

    class Meta:
        model = SelectiveTransferJob
        fields = ("source", "destination")
