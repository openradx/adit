from typing import Literal, TypedDict

from django.http import HttpRequest
from django_htmx.middleware import HtmxDetails
from rest_framework.request import Request

from adit.accounts.models import User


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


class AuthenticatedHttpRequest(HttpRequest):
    user: User


class AuthenticatedRequest(Request):
    user: User


class DicomLogEntry(TypedDict):
    level: Literal["Info", "Warning"]
    message: str
