import binascii
from datetime import datetime
from os import urandom

import pytz
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import models

from adit.accounts.models import User
from adit.core.models import AppSettings

from .utils.crypto import hash_token


class TokenSettings(AppSettings):
    token_length = 20
    fraction_length = 4

    class Meta:
        verbose_name_plural = "Token settings"


class TokenManager(models.Manager["Token"]):
    def create_token(
        self,
        user: AbstractBaseUser | AnonymousUser,
        client: str,
        expiry_time: datetime = datetime.now(),
    ):
        token_string = create_token_string()
        token_hashed = hash_token(token_string)
        token = self.create(
            token_hashed=token_hashed,
            fraction=token_string[: TokenSettings.fraction_length],
            author=user,
            client=client,
            expiry_time=expiry_time,
        )
        return token, token_string


class Token(models.Model):
    token_hashed = models.TextField(max_length=128)
    fraction = models.TextField(max_length=TokenSettings.fraction_length)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    client = models.TextField(max_length=100, unique=True)
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
        return self.token_hashed

    def is_expired(self):
        utc = pytz.UTC
        return self.expiry_time < utc.localize(datetime.now())


def create_token_string():
    return binascii.hexlify(urandom(int(TokenSettings.token_length))).decode()
