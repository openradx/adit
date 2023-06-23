import binascii
from datetime import datetime
from os import urandom

import pytz
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import models

from adit.accounts.models import User
from adit.core.models import AppSettings


class TokenSettings(AppSettings):
    token_lenght = 20

    class Meta:
        verbose_name_plural = "Token settings"


class TokenManager(models.Manager):
    def create_token(
        self,
        user: AbstractBaseUser | AnonymousUser,
        client: str = "",
        expiry_time: datetime = datetime.now(),
    ):
        token = create_token_string()
        token = self.create(
            token_string=token,
            author=user,
            client=client,
            expiry_time=expiry_time,
        )
        return token

    def user_is_owner(self, user: AbstractBaseUser | AnonymousUser, token_str: str):
        token = self.get(token_string=token_str)
        if token.author == user:
            return True
        else:
            return False


class Token(models.Model):
    token_string = models.TextField(max_length=TokenSettings.token_lenght + 10)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    client = models.TextField(max_length=100)
    expiry_time = models.DateTimeField()
    expires = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)

    objects = TokenManager()

    class Meta:
        permissions = [
            (
                "manage_auth_tokens",
                "Can manage REST authentication tokens",
            )
        ]

    def __str__(self):
        return self.token_string

    def is_expired(self):
        utc = pytz.UTC
        return self.expiry_time < utc.localize(datetime.now())

    # def __repr__(self):
    #    return self.token_string, f"{self.author.get_username()}"


def create_token_string():
    return binascii.hexlify(urandom(int(TokenSettings.token_lenght))).decode()
