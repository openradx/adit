from datetime import timedelta

import factory
from django.utils import timezone

from adit.core.factories import BaseDjangoModelFactory
from shared.accounts.factories import UserFactory

from .models import Token
from .utils.crypto import hash_token


class TokenFactory(BaseDjangoModelFactory[Token]):
    class Meta:
        model = Token
        django_get_or_create = ("token_hashed",)

    token_hashed = factory.LazyFunction(lambda: hash_token("test_token_string"))
    description = factory.Faker("sentence", nb_words=3)
    owner = factory.SubFactory(UserFactory)
    created_time = timezone.now()
    expires = timezone.now() + timedelta(hours=24)
    last_used = timezone.now()
