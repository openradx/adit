import factory

from .models import Token, create_token_string


class TokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Token
        django_get_or_create = ("token_string",)

    token_string = create_token_string
