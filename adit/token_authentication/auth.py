from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions

from .models import RestAuthToken


class RestTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token_str = request.META.get("Authorization", None)
        print(request.META)
        if token_str is None:
            message = "Invalid token header. Please provide credentials in the request header."
            raise exceptions.AuthenticationFailed(message)
        
        is_valid, message, user, token = self.verify_token(token_str)

        if not is_valid:
            raise exceptions.AuthenticationFailed(message)

        return (user, token)

    def verify_token(self, token_str):
        message = ""
        is_valid = True

        try:
            token = RestAuthToken.objects.filter(token_string=token_str)
            user = token.author

        except Exception as e:
            is_valid = False
            token = None
            user = None
            message = "Invalid token provided." + e
        
        # constrains
        if token.is_expired():
            is_valid = False
            message = "Token is expired."

        return is_valid, message, user, token
