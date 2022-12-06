from django import forms
from django.contrib import admin
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group
from .models import User
from ..groups.models import Access


class GroupForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        label='Users',
        queryset=User.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple(
            "users", is_stacked=False))
    accesses = forms.ModelMultipleChoiceField(
        label='Access',
        queryset=Access.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple(
            "accesses", is_stacked=False))
    
    class Meta:
        model = Group
        exclude = ()  # since Django 1.8 this is needed
        widgets = {
            'permissions': admin.widgets.FilteredSelectMultiple(
                "permissions", is_stacked=False),
        }


class CrispyAuthentificationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"
        self.helper.add_input(Submit("login", "Login"))


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "department",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("register", "Register"))
