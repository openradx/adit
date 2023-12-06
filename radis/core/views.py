from abc import ABC
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.core.exceptions import SuspiciousOperation
from django.forms import Form
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import re_path, reverse_lazy
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from revproxy.views import ProxyView

from .forms import BroadcastForm
from .models import CoreSettings
from .tasks import broadcast_mail
from .types import AuthenticatedHttpRequest, HtmxHttpRequest

THEME = "theme"


@staff_member_required
def admin_section(request: HttpRequest) -> HttpResponse:
    return render(request, "core/admin_section.html")


class HtmxTemplateView(TemplateView):
    def get(self, request: HtmxHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.htmx:
            raise SuspiciousOperation
        return super().get(request, *args, **kwargs)


class BroadcastView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = "core/broadcast.html"
    form_class = BroadcastForm
    success_url = reverse_lazy("broadcast")
    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def form_valid(self, form: Form) -> HttpResponse:
        subject = form.cleaned_data["subject"]
        message = form.cleaned_data["message"]

        broadcast_mail.delay(subject, message)

        messages.add_message(
            self.request,
            messages.SUCCESS,
            "Mail queued for sending successfully",
        )

        return super().form_valid(form)


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        core_settings = CoreSettings.get()
        assert core_settings
        context["announcement"] = core_settings.announcement
        return context


class BaseUpdatePreferencesView(ABC, LoginRequiredMixin, View):
    """Allows the client to update the user preferences.

    We use this to retain some form state between browser refreshes.
    The implementations of this view is called by some AJAX requests when specific
    form fields are changed.
    """

    allowed_keys: list[str]

    def post(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        for key in request.POST.keys():
            if key not in self.allowed_keys:
                raise SuspiciousOperation(f'Invalid preference "{key}" to update.')

        preferences = request.user.preferences

        for key, value in request.POST.items():
            if value == "true":
                value = True
            elif value == "false":
                value = False

            preferences[key] = value

        request.user.save()

        return HttpResponse()


class UpdatePreferencesView(BaseUpdatePreferencesView):
    allowed_keys = [THEME]


class AdminProxyView(LoginRequiredMixin, UserPassesTestMixin, ProxyView):
    """A reverse proxy view to hide other services behind that only an admin can access.

    By using a reverse proxy we can use the Django authentication
    to check for an logged in admin user.
    Code from https://stackoverflow.com/a/61997024/166229
    """

    request: AuthenticatedHttpRequest

    def test_func(self):
        return self.request.user.is_staff

    @classmethod
    def as_url(cls):
        return re_path(rf"^{cls.url_prefix}/(?P<path>.*)$", cls.as_view())  # type: ignore


class FlowerProxyView(AdminProxyView):
    upstream = f"http://{settings.FLOWER_HOST}:{settings.FLOWER_PORT}"  # type: ignore
    url_prefix = "flower"
    rewrite = ((rf"^/{url_prefix}$", rf"/{url_prefix}/"),)

    @classmethod
    def as_url(cls):
        # Flower needs a bit different setup then the other proxy views as flower
        # uses a prefix itself (see docker compose service)
        return re_path(rf"^(?P<path>{cls.url_prefix}.*)$", cls.as_view())
