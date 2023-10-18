from typing import Generic, TypeVar

import factory
from faker import Faker

from radis.accounts.factories import UserFactory

from .models import CollectedReport, Collection

fake = Faker()

T = TypeVar("T")


class BaseDjangoModelFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, *args, **kwargs) -> T:
        return super().create(*args, **kwargs)


class CollectionFactory(BaseDjangoModelFactory[Collection]):
    class Meta:
        model = Collection

    name = factory.Faker("sentence")
    owner = factory.SubFactory(UserFactory)


class CollectedReportFactory(BaseDjangoModelFactory[CollectedReport]):
    class Meta:
        model = CollectedReport

    document_id = factory.Faker("uuid4")
    collection = factory.SubFactory(CollectionFactory)
