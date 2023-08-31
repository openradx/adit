from typing import Any

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView

from adit.core.types import AuthenticatedHttpRequest

from .forms import RegistrationForm
from .models import User


class UserProfileView(LoginRequiredMixin, AccessMixin, TemplateView):
    template_name = "accounts/profile.html"
    request: AuthenticatedHttpRequest

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


class RegistrationView(CreateView):
    model = User
    form_class = RegistrationForm
    template_name = "accounts/registration.html"

    def form_valid(self, form: RegistrationForm) -> HttpResponse:
        form.instance.is_active = False
        return super().form_valid(form)
