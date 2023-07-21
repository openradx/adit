import binascii
from datetime import datetime
from os import urandom

import pytz
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import models

from adit.accounts.models import User
from adit.core.models import AppSettings


class TokenSettings(AppSettings):
    token_length = 20
    fraction_length = 4

    class Meta:
        verbose_name_plural = "Token settings"


class TokenManager(models.Manager):
    def create_token(
        self,
        user: AbstractBaseUser | AnonymousUser,
        client: str,
        expiry_time: datetime = datetime.now(),
    ):
        token_string_unhashed = create_token_string()
        token_string = make_password(token_string_unhashed)
        token = self.create(
            token_string=token_string,
            fraction=token_string_unhashed[: TokenSettings.fraction_length],
            author=user,
            client=client,
            expiry_time=expiry_time,
        )
        return token, token_string_unhashed


class Token(models.Model):
    token_string = models.TextField(max_length=128)
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
        return self.token_string

    def is_expired(self):
        utc = pytz.UTC
        return self.expiry_time < utc.localize(datetime.now())


def create_token_string():
    return binascii.hexlify(urandom(int(TokenSettings.token_length))).decode()
