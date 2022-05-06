from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView, View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import (
    PermissionRequiredMixin,
    LoginRequiredMixin,
)
from rest_framework.authtoken.views import ObtainAuthToken

from .models import RestAuthToken

import datetime
import json
import urllib.parse


class RestAuthView(
    LoginRequiredMixin,
    View,
):
    def get(self, request):
        template = "token_authentication/token_dashboard.html"

        tokens = RestAuthToken.objects.filter(author=request.user)
        expiry_times = RestAuthToken.objects.expiry_times

        context = {
            "User": request.user,
            "Tokens": tokens,
            "ExpiryTimes": expiry_times,
        }

        return render(request, template_name=template, context=context)


class RestAuthTokenListView(
    LoginRequiredMixin,
    View,
):
    def get(self, request):
        template = "token_authentication/_token_list.html"

        tokens = RestAuthToken.objects.filter(author=request.user)
        context = {
            "User": request.user,
            "Tokens": tokens,
        }
        return render(request, template, context=context)


@method_decorator(csrf_exempt, name='dispatch')
class RestAuthGenerateTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "token_authentication.manage_auth_tokens"
    
    def post(self, request):
        data = urllib.parse.parse_qs(request.body.decode("utf-8"))
        time_delta = RestAuthToken.objects.expiry_times[data["expiry_time"][0]]
        if not data["expiry_time"] == "never":
            expiry_time = datetime.datetime.now() + datetime.timedelta(hours=time_delta)
        
        if not "client" in list(data.keys()):
            # here: raise exception if client is required
            data["client"] = ["Undefined"]
      
        token = RestAuthToken.objects.create_token(
            user=request.user, 
            client=data["client"][0], 
            expiry_time=expiry_time
        )

        token_string = token.__str__()
        return HttpResponse(token_string)


@method_decorator(csrf_exempt, name='dispatch')
class RestAuthDeleteTokenView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
): 
    permission_required = "token_authentication.manage_auth_tokens"
    
    def post(self, request):
        data = urllib.parse.parse_qs(request.body.decode("utf-8"))
        token_strs = data["token_str"]
        for token_str in token_strs:
            try:
                token = RestAuthToken.objects.filter(token_string=token_str)[0]
            except IndexError:
                return HttpResponse(
                    json.dumps(
                        {
                            "sucess": False,
                            "message": "Did not find a matching token with ID: "
                            + token_str,
                        }
                    )
                )
            if token.author == request.user:
                RestAuthToken.objects.filter(token_string=token_str).delete()
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
