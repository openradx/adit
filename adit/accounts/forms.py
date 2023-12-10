from typing import Any

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import ValidationError

from .models import User, UserProfile


# TODO: fix, phone_number and department are in user profile and not user itself
class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "email",
            "first_name",
            "last_name",
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # In Django's AbstractUser (which django-registration-redux uses internally) the fields
        # email, first name and last name are not required. We fix this in our registration
        # form.
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        # Django's AbstractUser Email model field is not unique. We fix this here programmatically
        # at the form level.
        email: str = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this Email address is already registered.")

        return email


class UserProfileRegistrationForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = (
            "phone_number",
            "department",
        )


class RegistrationForm(UserRegistrationForm, UserProfileRegistrationForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("register", "Register"))
