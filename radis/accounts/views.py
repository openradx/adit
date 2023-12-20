from typing import Any

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.views import View
from django.views.generic import TemplateView

from radis.core.http import trigger_toast
from radis.core.types import AuthenticatedHttpRequest


class UserProfileView(LoginRequiredMixin, AccessMixin, TemplateView):
    template_name = "accounts/profile.html"
    request: AuthenticatedHttpRequest

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


class ActiveGroupView(LoginRequiredMixin, View):
    def post(self, request: AuthenticatedHttpRequest):
        if not request.htmx:
            raise SuspiciousOperation

        try:
            group_id = request.POST.get("group") or ""
            group_id = int(group_id)
        except ValueError:
            raise ValidationError("Invalid group ID")

        request.user.active_group = request.user.groups.get(id=group_id)
        request.user.save()

        return trigger_toast(
            title="Active group changed",
            text=f"Active group changed to {request.user.active_group.name}",
        )
