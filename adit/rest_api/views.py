from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from django.http import HttpResponse
from adit.token_authentication.auth import RestTokenAuthentication


# Create your views here.
class TestView(APIView):
    authentication_classes = [RestTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return HttpResponse("HI")