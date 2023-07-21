import datetime

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
    View,
):
    generate_token_form = GenerateTokenForm

    def get(self, request: HttpRequest):
        tokens = Token.objects.filter(author=request.user)

        context = {
            "User": request.user,
            "Tokens": tokens,
            "GenerateTokenForm": self.generate_token_form,
        }

        return render(
            request, template_name="token_authentication/token_dashboard.html", context=context
        )


class GenerateTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FormView,
):
    permission_required = "token_authentication.manage_auth_tokens"
    form_class = GenerateTokenForm

    def form_valid(self, form):
        data = form.cleaned_data
        time_delta = float(data["expiry_time"])
        expiry_time = datetime.datetime.now() + datetime.timedelta(hours=time_delta)
        if Token.objects.filter(author=self.request.user, client=data["client"]).exists():
            messages.error(self.request, "The token client must be unique.")
            return redirect("token_dashboard")
        try:
            _, token_string_unhashed = Token.objects.create_token(
                user=self.request.user, client=data["client"], expiry_time=expiry_time
            )
        except Exception as e:
            messages.error(self.request, str(e))
            return redirect("token_dashboard")
        messages.success(self.request, token_string_unhashed)
        return redirect("token_dashboard")


class DeleteTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "token_authentication.manage_auth_tokens"

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
