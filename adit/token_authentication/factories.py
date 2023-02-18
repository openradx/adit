import factory
from .models import RestAuthToken, create_token_string


class RestAuthTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RestAuthToken
        django_get_or_create = ("token_string",)

    token_string = create_token_string
