import datetime
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.views.generic import FormView, View
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import GenerateTokenForm
from .models import Token


class TokenDashboardView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "token_authentication.view_token"

    def get(self, request: HttpRequest):
        new_token = request.session.pop("new_token", None)
        tokens = Token.objects.filter(author=request.user)

        context = {
            "new_token": new_token,
            "tokens": tokens,
            "generate_token_form": GenerateTokenForm(user=request.user),
        }

        return render(
            request, template_name="token_authentication/token_dashboard.html", context=context
        )


class GenerateTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FormView,
):
    permission_required = "token_authentication.add_token"
    form_class = GenerateTokenForm

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        expiry_time = int(data["expiry_time"])
        expires = None
        if expiry_time > 0:
            expires = datetime.datetime.now() + datetime.timedelta(hours=expiry_time)
        if Token.objects.filter(author=self.request.user, client=data["client"]).exists():
            messages.error(self.request, "The token client must be unique.")
            return redirect("token_dashboard")
        try:
            _, token_string = Token.objects.create_token(
                user=self.request.user, client=data["client"], expires=expires
            )
        except Exception as err:
            messages.error(self.request, str(err))
            return redirect("token_dashboard")

        self.request.session["new_token"] = token_string
        return redirect("token_dashboard")


class DeleteTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "token_authentication.delete_token"

    def post(self, request: HttpRequest):
        data = request.POST
        client = data["client"]
        token = Token.objects.get(client=client)
        client = token.client

        token.delete()
        return redirect("token_dashboard")


class TestView(APIView):
    def get(self, request: Request):
        return Response({"message": "OK"})
