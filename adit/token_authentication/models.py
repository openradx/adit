import binascii
from datetime import datetime
from os import urandom

import pytz
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import models
from django.db.models.constraints import UniqueConstraint

from adit.accounts.models import User

from .utils.crypto import hash_token

TOKEN_LENGTH = 20  # Length of the unhashed token
FRACTION_LENGTH = 4  # Length of the token hint visible to the user in the table


class TokenManager(models.Manager["Token"]):
    def create_token(
        self,
        user: AbstractBaseUser | AnonymousUser,
        client: str,
        expires: datetime | None,
    ):
        token_string = binascii.hexlify(urandom(TOKEN_LENGTH)).decode()
        token_hashed = hash_token(token_string)
        token = self.create(
            token_hashed=token_hashed,
            fraction=token_string[:FRACTION_LENGTH],
            owner=user,
            client=client,
            expires=expires,
        )
        return token, token_string


class Token(models.Model):
    token_hashed = models.CharField(max_length=128, unique=True)
    fraction = models.CharField(max_length=FRACTION_LENGTH)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_time = models.DateTimeField(auto_now_add=True)
    client = models.CharField(max_length=100)
    expires = models.DateTimeField(blank=True, null=True)
    last_used = models.DateTimeField(blank=True, null=True)

    objects = TokenManager()

    class Meta:
        permissions = [
            (
                "can_generate_never_expiring_token",
                "Can generate never expiring token",
            )
        ]
        constraints = [UniqueConstraint(fields=["client", "owner"], name="unique_client_per_user")]

    def __str__(self):
        return self.token_hashed

    def is_expired(self):
        utc = pytz.UTC
        return self.expires and self.expires < utc.localize(datetime.now())
