from django.db import models
from django.utils import timezone

from adit.accounts.models import User

import datetime
import binascii
from os import urandom

# Settings
TOKEN_LENGHT = 20


class RestAuthTokenManager(models.Manager):
    
    expiry_times = {
        "1 Hour": 1,
        "1 Day": 24,
        "7 Days": 168,
        "30 Days": 720,
    }

    def create_token(self, user, client="", expiry_time=datetime.datetime.now()):
        token = _create_token_string()
        token = self.create(
            token_string=token,
            author=user,
            client=client,
            expiry_time=expiry_time,
        )
        return token

    def user_is_owner(self, user, token_str):
        token = self.filter(token_string=token_str)
        if token.author == user:
            return True
        else:
            return False


class RestAuthToken(models.Model):
    class Meta:
        permissions = [
            (
                "manage_auth_tokens",
                "Can manage REST authentication tokens",
            )
        ]

    token_string = models.TextField(max_length=TOKEN_LENGHT + 10)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    client = models.TextField(max_length=100)
    expiry_time = models.DateTimeField()
    expires = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)

    objects = RestAuthTokenManager()

    def __str__(self):
        return self.token_string

    def is_expired(self):
        return self.expiry_time < datetime.datetime.now()

    # def __repr__(self):
    #    return self.token_string, f"{self.author.get_username()}"


def _create_token_string():
    return binascii.hexlify(urandom(int(TOKEN_LENGHT))).decode()
