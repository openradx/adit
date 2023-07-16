from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import (
    UserPassesTestMixin,
)
from django.shortcuts import render
from django.urls import re_path, reverse_lazy
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from revproxy.views import ProxyView

from radis.core.utils.permission_utils import is_logged_in_user

from .forms import BroadcastForm
from .models import CoreSettings
from .tasks import broadcast_mail


@staff_member_required
def sandbox(request):
    messages.add_message(request, messages.SUCCESS, "This message is server generated!")
    return render(request, "core/sandbox.html", {})


@staff_member_required
def admin_section(request):
    return render(request, "core/admin_section.html", {})


class BroadcastView(UserPassesTestMixin, FormView):
    template_name = "core/broadcast.html"
    form_class = BroadcastForm
    success_url = reverse_lazy("broadcast")

    def test_func(self):
        user = self.request.user
        if is_logged_in_user(user):
            return user.is_staff

        return False

    def form_valid(self, form):
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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        core_settings = CoreSettings.get()
        assert core_settings
        context["announcement"] = core_settings.announcement
        return context


class AdminProxyView(UserPassesTestMixin, ProxyView):
    """A reverse proxy view to hide other services behind that only an admin can access.

    By using a reverse proxy we can use the Django authentication
    to check for an logged in admin user.
    Code from https://stackoverflow.com/a/61997024/166229
    """

    def test_func(self):
        user = self.request.user
        if is_logged_in_user(user):
            return user.is_staff

        return False

    @classmethod
    def as_url(cls):
        return re_path(rf"^{cls.url_prefix}/(?P<path>.*)$", cls.as_view())  # type: ignore


class RabbitManagementProxyView(AdminProxyView):
    upstream = (
        f"http://{settings.RABBIT_MANAGEMENT_HOST}:",
        f"{settings.RABBIT_MANAGEMENT_PORT}",  # type: ignore
    )
    url_prefix = "rabbit"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)


class FlowerProxyView(AdminProxyView):
    upstream = f"http://{settings.FLOWER_HOST}:{settings.FLOWER_PORT}"  # type: ignore
    url_prefix = "flower"
    rewrite = ((rf"^/{url_prefix}$", rf"/{url_prefix}/"),)

    @classmethod
    def as_url(cls):
        # Flower needs a bit different setup then the other proxy views as flower
        # uses a prefix itself (see docker compose service)
        return re_path(rf"^(?P<path>{cls.url_prefix}.*)$", cls.as_view())
