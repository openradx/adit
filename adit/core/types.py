from typing import Literal, TypedDict

from django.http import HttpRequest
from django_htmx.middleware import HtmxDetails
from rest_framework.request import Request

from adit.accounts.models import User
from adit.core.models import DicomTask


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


class AuthenticatedHttpRequest(HtmxHttpRequest):
    user: User


class AuthenticatedApiRequest(Request):
    user: User


class DicomLogEntry(TypedDict):
    level: Literal["Info", "Warning"]
    title: str
    message: str


class ProcessingResult(TypedDict):
    status: DicomTask.Status
    message: str
    log: str
