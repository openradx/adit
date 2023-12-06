from django.http import HttpRequest
from django_htmx.middleware import HtmxDetails
from rest_framework.request import Request

from radis.accounts.models import User


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


class AuthenticatedHttpRequest(HtmxHttpRequest):
    user: User


class AuthenticatedRequest(Request):
    user: User
