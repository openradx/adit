from typing import cast

import factory
from django.contrib.auth.models import Group

from adit_radis_shared.common.factories import BaseDjangoModelFactory

from .models import User


class UserFactory(BaseDjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone_number = factory.Faker("phone_number")
    department = factory.Faker("company")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        user = cast(User, obj)
        if extracted:
            user.set_password(extracted)
        else:
            user.set_password("userpass")

        if create:
            user.save()


class AdminUserFactory(UserFactory):
    username = "admin"
    email = "admin@openradx.test"
    is_superuser = True
    is_staff = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        user = cast(User, obj)
        if extracted:
            user.set_password(extracted)
        else:
            user.set_password("admin")

        if create:
            user.save()


class GroupFactory(BaseDjangoModelFactory[Group]):
    class Meta:
        model = Group
        django_get_or_create = ("name",)

    name = factory.Faker("company")
