import factory

from ...factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
)
from .models import ExampleTransferJob, ExampleTransferTask


class ExampleTransferJobFactory(AbstractTransferJobFactory[ExampleTransferJob]):
    class Meta:
        model = ExampleTransferJob


class ExampleTransferTaskFactory(AbstractTransferTaskFactory[ExampleTransferTask]):
    class Meta:
        model = ExampleTransferTask

    job = factory.SubFactory(ExampleTransferJobFactory)
