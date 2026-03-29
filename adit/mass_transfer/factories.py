import factory
from django.utils import timezone

from adit.core.factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
)

from .models import MassTransferJob, MassTransferTask


class MassTransferJobFactory(AbstractTransferJobFactory[MassTransferJob]):
    class Meta:
        model = MassTransferJob

    start_date = factory.LazyFunction(lambda: timezone.now().date())
    end_date = factory.LazyFunction(lambda: timezone.now().date())


class MassTransferTaskFactory(AbstractTransferTaskFactory[MassTransferTask]):
    class Meta:
        model = MassTransferTask

    job = factory.SubFactory(MassTransferJobFactory)
    partition_start = factory.LazyFunction(timezone.now)
    partition_end = factory.LazyFunction(timezone.now)
    partition_key = factory.Faker("date", pattern="%Y-%m-%d")
