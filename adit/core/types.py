from django.http import HttpRequest

from adit.accounts.models import User


class AuthenticatedHttpRequest(HttpRequest):
    user: User
