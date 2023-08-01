import datetime
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError
from django.views.generic import DeleteView, FormView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from adit.core.mixins import OwnerRequiredMixin

from .forms import GenerateTokenForm
from .models import Token


class TokenDashboardView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FormView,
):
    template_name = "token_authentication/token_dashboard.html"
    form_class = GenerateTokenForm
    success_url = "/token-authentication/"
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
            _, token_string = Token.objects.create_token(
                user=self.request.user, client=data["client"], expires=expires
            )
        except IntegrityError:
            form.add_error("client", "The token client must be unique")
            return super().form_invalid(form)
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
    OwnerRequiredMixin,
    DeleteView,
):
    permission_required = "token_authentication.delete_token"
    model = Token
    success_url = "/token-authentication/"


class TestView(APIView):
    def get(self, request: Request):
        return Response({"message": "OK"})
