import logging

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from adit_radis_shared.accounts.models import User

from .models import Token
from .utils.crypto import hash_token, verify_token

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

        token.last_used = timezone.now()
        token.save()

        return (user, token)

    def verify_token(self, token_string: str) -> tuple[str, User | None, Token | None]:
        """
        This method verifies the token string by checking if the token
        exists in the database and if the token is not expired.

        :param token_string: The token string to be verified.
        :return: A tuple containing a message describing the result of the
        verification, the user associated with the token, and the token
        object itself. If the token is invalid, the user and token objects
        are None.
        """
        token_hashed = hash_token(token_string)

        try:
            token = Token.objects.get(token_hashed=token_hashed)
        except Token.DoesNotExist:
            return "Invalid token. Token does not exist.", None, None

        # Double check that the token hash is correct.
        if not verify_token(token_string, token.token_hashed):
            raise AssertionError(f"Internal token error. Invalid token hash {token_hashed}.")

        if token.is_expired():
            return "Invalid Token. Token is expired.", None, None

        return "", token.owner, token
