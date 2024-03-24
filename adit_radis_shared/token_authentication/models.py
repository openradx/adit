import binascii
from datetime import datetime
from os import urandom

import pytz
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import models

from adit_radis_shared.accounts.models import User

from .utils.crypto import hash_token

TOKEN_LENGTH = 20  # Length of the unhashed token
FRACTION_LENGTH = 4  # Length of the token hint visible to the user in the table


class TokenManager(models.Manager["Token"]):
    def create_token(
        self,
        user: AbstractBaseUser | AnonymousUser,
        description: str,
        expires: datetime | None,
    ):
        token_string = binascii.hexlify(urandom(TOKEN_LENGTH)).decode()
        token_hashed = hash_token(token_string)
        token = self.create(
            owner=user,
            token_hashed=token_hashed,
            fraction=token_string[:FRACTION_LENGTH],
            description=description,
            expires=expires,
        )
        return token, token_string


class Token(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    token_hashed = models.CharField(max_length=128, unique=True)
    fraction = models.CharField(max_length=FRACTION_LENGTH)
    description = models.CharField(blank=True, max_length=120)
    expires = models.DateTimeField(blank=True, null=True)
    created_time = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(blank=True, null=True)

    objects: TokenManager = TokenManager()

    class Meta:
        permissions = [
            (
                "can_generate_never_expiring_token",
                "Can generate never expiring token",
            )
        ]

    def __str__(self):
        return self.token_hashed

    def is_expired(self):
        utc = pytz.UTC
        return self.expires and self.expires < utc.localize(datetime.now())
