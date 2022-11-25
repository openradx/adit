from django.http import HttpResponse
from redis import AuthenticationError
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions

from .models import RestAuthToken


class RestTokenAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Authentication failed."

    def authenticate(self, request):

        try:
            protocol, token_str = request.META["HTTP_AUTHORIZATION"].split(" ")
        except Exception as e:
            message = "Invalid token header. Please provide credentials in the request header."
            raise exceptions.AuthenticationFailed(message)
        if not protocol == "Token":
            message = "Please use the token authentication protocol to access the REST API."
            raise exceptions.AuthenticationFailed(message)

        is_valid, message, user, token = self.verify_token(token_str)

        if not is_valid:
            raise exceptions.AuthenticationFailed(message)

        token.save()  # updates the last-used attribute
        return (user, token)

    def verify_token(self, token_str):
        
        message = ""
        is_valid = True

        tokens = RestAuthToken.objects.filter(token_string=token_str)

        if not len(tokens) == 1:
            message = "Invalid Token. Please make sure exactly one matching token entity exists."
            Exc = exceptions.AuthenticationFailed(detail=message)
            print(Exc.detail)
            raise Exc
        
        token = tokens[0]
        user = token.author

        # constrains
        if token.is_expired():
            is_valid = False
            message = "Invalid Token. Token is expired."

        return is_valid, message, user, token
