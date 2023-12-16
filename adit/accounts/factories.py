from typing import Generic, TypeVar

import factory
from django.contrib.auth.models import Group

from .models import User

T = TypeVar("T")


# We can't use BaseDjangoModelFactory of adit.core.factories because of circular imports
class BaseDjangoModelFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, *args, **kwargs) -> T:
        return super().create(*args, **kwargs)


class UserFactory(BaseDjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "userpass")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone_number = factory.Faker("phone_number")
    department = factory.Faker("company")


class AdminUserFactory(UserFactory):
    username = "admin"
    email = "admin@adit.test"
    password = factory.PostGenerationMethodCall("set_password", "admin")
    is_superuser = True
    is_staff = True


class GroupFactory(BaseDjangoModelFactory[Group]):
    class Meta:
        model = Group
        django_get_or_create = ("name",)

    name = factory.Faker("company")
