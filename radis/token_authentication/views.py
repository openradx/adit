import datetime
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import DeleteView, FormView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from radis.core.types import AuthenticatedHttpRequest

from .forms import GenerateTokenForm
from .models import Token


class TokenDashboardView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FormView,
):
    template_name = "token_authentication/token_dashboard.html"
    form_class = GenerateTokenForm
    success_url = reverse_lazy("token_dashboard")
    permission_required = (
        "token_authentication.view_token",
        "token_authentication.add_token",
    )

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        expiry_time = int(data["expiry_time"])
        expires = None
        if expiry_time > 0:
            expires = datetime.datetime.now() + datetime.timedelta(hours=expiry_time)
        try:
            description: str = data["description"]
            _, token_string = Token.objects.create_token(
                user=self.request.user,
                description=description,
                expires=expires,
            )
        except Exception as err:
            form.add_error(None, str(err))
            return super().form_invalid(form)

        self.request.session["new_token"] = token_string
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        new_token = self.request.session.pop("new_token", None)
        tokens = Token.objects.filter(owner=self.request.user)

        context.update({"new_token": new_token, "tokens": tokens})

        return context


class DeleteTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DeleteView,
):
    permission_required = "token_authentication.delete_token"
    model = Token
    success_url = reverse_lazy("token_dashboard")
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)


class TestView(APIView):
    def get(self, request: Request):
        return Response({"message": "OK"})
