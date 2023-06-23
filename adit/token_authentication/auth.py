from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from .models import Token


class RestTokenAuthentication(BaseAuthentication):
    """
    This class is used to authenticate users via a json web token.
    The token is expected to be provided in the request header as follows:
    Authorization: Token <token_string>
    """

    def authenticate_header(self, request: Request):
        return "Authentication failed."

    def authenticate(self, request: Request):
        print(request.META)
        try:
            auth = request.META.get("HTTP_AUTHORIZATION", None)
            if auth is None:
                auth = request.META["headers"].get("Authorization", None)
            protocol, token_str = auth.split(" ")
        except Exception:
            message = "Invalid token header. Please provide credentials in the request header."
            raise AuthenticationFailed(message)

        if not protocol == "Token":
            message = "Please use the token authentication protocol to access the REST API."
            raise AuthenticationFailed(message)

        is_valid, message, user, token = self.verify_token(token_str)
        if not is_valid:
            print("token is not valid")
            raise AuthenticationFailed(message)

        token.save()  # updates the last-used attribute
        return (user, token)

    def verify_token(self, token_str: str):
        message = ""
        is_valid = True

        tokens = Token.objects.filter(token_string=token_str)
        if len(tokens) == 0:
            is_valid = False
            message = "Invalid Token. Token does not exist."
            return is_valid, message, None, None

        token = tokens[0]
        user = token.author

        # constrains
        if token.is_expired():
            is_valid = False
            message = "Invalid Token. Token is expired."

        return is_valid, message, user, token
