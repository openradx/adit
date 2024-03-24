from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Layout, Submit
from django import forms

from adit_radis_shared.accounts.models import User

from .models import Token

EXPIRY_TIMES = (
    (24, "1 Day"),
    (7 * 24, "7 Days"),
    (30 * 24, "30 Days"),
    (90 * 24, "90 Days"),
)


class GenerateTokenForm(forms.ModelForm):
    class Meta:
        model = Token
        fields = ["description"]

    def __init__(self, *args, **kwargs):
        self.user: User = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        expiry_times = EXPIRY_TIMES
        if self.user.has_perm("token_authentication.can_generate_never_expiring_token"):
            expiry_times = expiry_times + ((0, "Never"),)

        self.fields["expiry_time"] = forms.ChoiceField(choices=expiry_times, label="Expiry Time")

        self.fields["description"].widget.attrs["placeholder"] = "Optional"

        self.helper = FormHelper(self)
        self.helper.form_id = "generate_token_form"
        self.helper.add_input(Submit("save", "Generate Token"))
        self.helper.layout = Layout(
            Div(
                Div(
                    Field("expiry_time"),
                    css_class="col-3",
                ),
                Div(
                    Field("description"),
                    css_class="col-9",
                ),
                css_class="row",
            ),
        )

    def clean_expiry_time(self):
        expiry_time = self.cleaned_data["expiry_time"]
        if not self.user.has_perm("token_authentication.can_generate_never_expiring_token"):
            if expiry_time == "0":
                raise forms.ValidationError(
                    "You do not have permission to generate never expiring tokens."
                )

        return expiry_time
