import logging
from typing import Tuple

from django.contrib.auth.hashers import check_password
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from adit.accounts.models import User

from .models import Token

logger = logging.getLogger(__name__)


class RestTokenAuthentication(BaseAuthentication):
    """
    This class is used to authenticate users via a json web token.
    The token is expected to be provided in the request header as follows:
    Authorization: Token <token_string>
    """

    def authenticate_header(self, request: Request):
        return "Authentication failed."

    def authenticate(self, request: Request):
        try:
            auth = request.META.get("HTTP_AUTHORIZATION", None)
            if auth is None:
                auth = request.META["headers"].get("Authorization", None)
            protocol, token_string = auth.split(" ")
        except Exception:
            message = "Invalid token header. Please provide credentials in the request header."
            raise AuthenticationFailed(message)

        if not protocol == "Token":
            message = "Please use the token authentication protocol to access the REST API."
            raise AuthenticationFailed(message)

        message, user, token = self.verify_token(token_string)
        if token is None:
            raise AuthenticationFailed(message)

        token.save()  # updates the last-used attribute

        return (user, token)

    def verify_token(self, token_string: str) -> Tuple[str, User | None, Token | None]:
        """
        This method verifies the token string by checking if the token
        exists in the database and if the token is not expired.

        :param token_string: The token string to be verified.
        :return: A tuple containing a message describing the result of the
        verification, the user associated with the token, and the token
        object itself. If the token is invalid, the user and token objects
        are None.
        """
        message = ""

        tokens = Token.objects.all()

        matching_token = None
        for token in tokens:
            if check_password(token_string, token.token_string):
                matching_token = token
                break
        if matching_token is None:
            message = "Invalid Token. Token does not exist."
            return message, None, None

        token = matching_token
        user = token.author

        if token.is_expired():
            message = "Invalid Token. Token is expired."
            return message, None, None

        return message, user, token
