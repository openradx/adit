from typing import Any

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.views.generic import TemplateView

from radis.core.types import AuthenticatedHttpRequest


class UserProfileView(LoginRequiredMixin, AccessMixin, TemplateView):
    template_name = "accounts/profile.html"
    request: AuthenticatedHttpRequest

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context
