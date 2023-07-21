from datetime import timedelta
from functools import partial

import factory
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from adit.accounts.factories import UserFactory

from .models import Token


class TokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Token
        django_get_or_create = ("token_string",)

    token_string = factory.LazyFunction(partial(make_password, "test_token_string"))
    author = factory.SubFactory(UserFactory)
    created_time = timezone.now()
    client = factory.Faker("word")
    expiry_time = timezone.now() + timedelta(hours=24)
    expires = True
    last_used = timezone.now()
