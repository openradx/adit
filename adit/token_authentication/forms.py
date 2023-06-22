from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms


class GenerateTokenForm(forms.Form):
    EXPIRY_TIMES = (
        (1 / 60, "1 Minute"),
        (1, "1 Hour"),
        (24, "1 Day"),
        (168, "7 Days"),
        (720, "30 Days"),
    )
    expiry_time = forms.ChoiceField(choices=EXPIRY_TIMES, required=True, label="Expiry Time")
    client = forms.CharField(
        max_length=64,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_id = "token_form"
