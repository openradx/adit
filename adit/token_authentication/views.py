import datetime
import json
import urllib.parse

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import ListView, View
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import GenerateTokenForm
from .models import Token


class TokenDashboardView(
    LoginRequiredMixin,
    View,
):
    def get(self, request: HttpRequest):
        tokens = Token.objects.filter(author=request.user)
        form = GenerateTokenForm()

        context = {
            "User": request.user,
            "Tokens": tokens,
            "Form": form,
        }

        return render(
            request, template_name="token_authentication/token_dashboard.html", context=context
        )


class ListTokenView(
    LoginRequiredMixin,
    ListView,
):
    def get(self, request: HttpRequest):
        template = "token_authentication/_token_list.html"

        tokens = Token.objects.filter(author=request.user)
        context = {
            "User": request.user,
            "Tokens": tokens,
        }
        return render(request, template, context=context)


class GenerateTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "token_authentication.manage_auth_tokens"

    def post(self, request: HttpRequest):
        data = urllib.parse.parse_qs(request.body.decode("utf-8"))
        time_delta = float(data["expiry_time"][0])
        expiry_time = datetime.datetime.now() + datetime.timedelta(hours=time_delta)

        if "client" not in list(data.keys()):
            # here: raise exception if client is required
            data["client"] = ["Undefined"]

        token = Token.objects.create_token(
            user=request.user, client=data["client"][0], expiry_time=expiry_time
        )

        token_string = token.__str__()
        return HttpResponse(token_string)


class DeleteTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "token_authentication.manage_auth_tokens"

    def post(self, request: HttpRequest):
        data = urllib.parse.parse_qs(request.body.decode("utf-8"))
        token_strs = data["token_str"]
        for token_str in token_strs:
            try:
                token = Token.objects.filter(token_string=token_str)[0]
            except IndexError:
                return HttpResponse(
                    json.dumps(
                        {
                            "sucess": False,
                            "message": "Did not find a matching token with ID: " + token_str,
                        }
                    )
                )
            if token.author == request.user:
                Token.objects.filter(token_string=token_str).delete()
                return HttpResponse(
                    json.dumps(
                        {
                            "sucess": True,
                            "message": "Deleted token with ID: " + token_str,
                        }
                    )
                )
            else:
                return HttpResponse(
                    json.dumps(
                        {
                            "sucesss": False,
                            "message": "Could not delete token with ID: " + token_str,
                        }
                    )
                )


class TestView(APIView):
    def get(self, request: Request):
        return Response({"message": "OK"})
