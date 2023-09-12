from typing import Generic, TypeVar

import factory
from faker import Faker

fake = Faker()

T = TypeVar("T")


class BaseDjangoModelFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, *args, **kwargs) -> T:
        return super().create(*args, **kwargs)
