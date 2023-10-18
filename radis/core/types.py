from django.http import HttpRequest
from rest_framework.request import Request

from radis.accounts.models import User


class AuthenticatedHttpRequest(HttpRequest):
    user: User
    htmx: bool


class AuthenticatedRequest(Request):
    user: User
