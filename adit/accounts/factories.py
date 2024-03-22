from typing import Generic, TypeVar, cast

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
    email = "admin@adit.test"
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
