from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from .forms import CrispyAuthentificationForm

class LoginViewWithSuccessMsg(SuccessMessageMixin, LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CrispyAuthentificationForm
    success_message = "You were successfully logged in"