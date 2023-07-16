from typing import Generic, TypeVar

import factory
from faker import Faker

from radis.accounts.factories import UserFactory
from radis.core.models import ReportCollection, SavedReport

fake = Faker()

T = TypeVar("T")


class BaseDjangoModelFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, *args, **kwargs) -> T:
        return super().create(*args, **kwargs)


class ReportCollectionFactory(BaseDjangoModelFactory[ReportCollection]):
    class Meta:
        model = ReportCollection

    name = factory.Faker("sentence")
    note = factory.Faker("paragraph")
    owner = factory.SubFactory(UserFactory)


class SavedReportFactory(BaseDjangoModelFactory[SavedReport]):
    class Meta:
        model = SavedReport

    report_id = factory.Faker("uuid4")
    note = factory.Faker("paragraph")
    collection = factory.SubFactory(ReportCollectionFactory)
