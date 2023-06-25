from datetime import timedelta

import factory
from django.utils import timezone

from adit.accounts.factories import UserFactory

from .models import Token, create_token_string


class TokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Token
        django_get_or_create = ("token_string",)

    token_string = factory.LazyFunction(create_token_string)
    author = factory.SubFactory(UserFactory)
    created_time = timezone.now()
    client = factory.Faker("word")
    expiry_time = timezone.now() + timedelta(hours=24)
    expires = True
    last_used = timezone.now()
